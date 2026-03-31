package org.example.roaddetection.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.example.roaddetection.Listener.RoadInfoListener;
import org.example.roaddetection.events.AiResultEvent;
import org.example.roaddetection.events.DefectDetectedEvent;
import org.example.roaddetection.dto.AiDetectionItem;
import org.example.roaddetection.dto.AiPredictResponse;
import org.example.roaddetection.entity.DefectDetail;
import org.example.roaddetection.entity.InspectionImage;
import org.example.roaddetection.events.RoadInfoUpdateEvent;
import org.example.roaddetection.mapper.DefectDetailMapper;
import org.example.roaddetection.mapper.InspectionImageMapper;
import org.example.roaddetection.mapper.InspectionTaskMapper;
import org.example.roaddetection.util.GpsOffsetUtil;
import org.example.roaddetection.util.PathUtil;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.context.event.EventListener;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;
import cn.hutool.json.JSONUtil;
import org.example.roaddetection.entity.DefectEntity;
import org.example.roaddetection.mapper.DefectEntityMapper;
import org.example.roaddetection.util.FeatureUtil;

import java.io.File;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Slf4j
@Service
@RequiredArgsConstructor
public class DroneService {

    private final InspectionImageMapper imageMapper;
    private final DefectDetailMapper detailMapper;
    private final InspectionTaskMapper inspectionTaskMapper;
    private final DefectEntityMapper entityMapper;

    private final DroneAsyncService droneAsyncService;
    private final initImageService initImageService;

    private final ApplicationEventPublisher publisher;

    @Value("${drone.origin-dir}")
    private String originDir;

    /**
     * 【主线程同步入口】：处理文件上传、本地保存、数据库初始化占位
     */
    public void processUploadSync(Long taskId,
                                  Long droneId,
                                  Double lng,
                                  Double lat,
                                  Double altitude,
                                  Double yaw,
                                  Double pitch,
                                  Double roll,
                                  Double fov,
                                  MultipartFile file) throws Exception {
        log.info("【图片接收】无人机:{} 坐标:({}, {})", droneId, lng, lat);
        LocalDateTime now = LocalDateTime.now();

        String originalAbsolutePath = saveOriginalImage(file);
        String originalUrl = PathUtil.extractRelativePath(originalAbsolutePath, "origin/");
        Long imageId = initImageService.initImageRecord(taskId, droneId, lng, lat, originalUrl, now);

        droneAsyncService.processAiAsync(imageId, originalAbsolutePath, taskId, lng, lat, altitude, yaw, pitch, roll, fov);
    }


    /**
     * 监听 AI 处理结果事件
     */
    @Async("aiTaskExecutor")
    @EventListener
    @Transactional(rollbackFor = Exception.class)
    public void onAiResult(AiResultEvent event) {
        if (event.isSuccess()) {
            saveDetectionResult(event);
        } else {
            markAsFailed(event.getImageId(), event.getErrorMsg());
        }
    }

    /**
     * 保存原始图片到本地磁盘
     */
    private String saveOriginalImage(MultipartFile file) throws Exception {
        String date = LocalDate.now().toString();
        String fileName = UUID.randomUUID().toString().replace("-", "").substring(0, 8) + ".jpg";
        String saveDir = originDir + "/" + date;

        File dir = new File(saveDir);
        if (!dir.exists() && !dir.mkdirs()) {
            throw new RuntimeException("无法创建目录: " + saveDir);
        }

        String absolutePath = saveDir + "/" + fileName;
        file.transferTo(new File(absolutePath));
        return absolutePath;
    }

    /**
     * AI 处理成功后，将检测结果写入数据库
     */
    private void saveDetectionResult(AiResultEvent event) {
        AiPredictResponse aiResult = event.getAiResult();
        Long imageId = event.getImageId();
        boolean hasDefect = aiResult.getDetections_num() > 0;
        String resultUrl = PathUtil.extractRelativePath(event.getAiResult().getFilePath(), "result/");

        InspectionImage image = imageMapper.selectById(imageId);
        if (image == null) {
            log.error("【数据异常】找不到对应的图片记录，ID: {}", imageId);
            return;
        }

        image.setResultImageUrl(resultUrl);
        image.setIsDefect(hasDefect ? 1 : 0);
        image.setDefectCount(aiResult.getDetections_num());
        image.setStatus("DONE");
        imageMapper.updateById(image);

        if (hasDefect) {
            saveDefectDetails(imageId, event);
            inspectionTaskMapper.increaseDefectCount(event.getTaskId(), aiResult.getDetections_num());
            publisher.publishEvent(new DefectDetectedEvent(event.getTaskId(), event.getLng(), event.getLat(), event.getAiResult(), resultUrl));
            log.info("【检测完成】发现病害 {} 处，图片ID: {}", aiResult.getDetections_num(), imageId);
        } else {
            log.info("【检测通过】该坐标无病害，图片ID: {}", imageId);
        }
    }

    /**
     * 保存病害详情列表
     */
    @Transactional(rollbackFor = Exception.class)
    public void saveDefectDetails(Long imageId, AiResultEvent event) {
        AiPredictResponse aiResult = event.getAiResult();
        if (aiResult.getDetections() == null || aiResult.getDetections().isEmpty()) {
            return;
        }

        // 1. 【粗筛】范围查找 (约 5-10 米)
        double range = 0.0001;
        List<DefectEntity> nearbyEntities = entityMapper.selectList(
                new LambdaQueryWrapper<DefectEntity>()
                        .between(DefectEntity::getLng, event.getLng() - range, event.getLng() + range)
                        .between(DefectEntity::getLat, event.getLat() - range, event.getLat() + range)
        );

        for (AiDetectionItem item : aiResult.getDetections()) {
            double[] realGps = GpsOffsetUtil.calculateRealGps(
                    event.getLng(),
                    event.getLat(),
                    event.getYaw(),
                    event.getPitch(),
                    event.getRoll(),
                    event.getAltitude(),
                    event.getFov(),
                    aiResult.getImageWidth(),
                    aiResult.getImageHeight(),
                    item.getBbox()
            );
            double realLng = realGps[0];
            double realLat = realGps[1];
            Long matchedEntityId = null;

            // 2. 【细筛】特征比对
            for (DefectEntity entity : nearbyEntities) {
                // 查找该实体关联的最新一条详情
                DefectDetail lastDetail = detailMapper.selectOne(
                        new LambdaQueryWrapper<DefectDetail>()
                                .eq(DefectDetail::getEntityId, entity.getId())
                                .orderByDesc(DefectDetail::getId)
                                .last("LIMIT 1")
                );

                if (lastDetail != null && lastDetail.getFeatureVector() != null) {
                    // --- 使用 Hutool 解析 JSON ---
                    List<Float> oldFeature = JSONUtil.toList(lastDetail.getFeatureVector(), Float.class);

                    double similarity = FeatureUtil.cosineSimilarity(item.getFeature(), oldFeature);

                    if (similarity > 0.85) {
                        matchedEntityId = entity.getId();
                        log.info("【匹配成功】实体ID: {}, 相似度: {}", matchedEntityId, similarity);
                        break;
                    }
                }
            }

            // 3. 【决策】
            if (matchedEntityId == null) {
                DefectEntity newEntity = new DefectEntity();
                newEntity.setDefectType(item.getClass_name());
                newEntity.setLng(realLng);
                newEntity.setLat(realLat);
                newEntity.setStatus("ACTIVE");
                newEntity.setCreateTime(LocalDateTime.now());
                entityMapper.insert(newEntity);
                matchedEntityId = newEntity.getId();
            }

            // 4. 保存详情
            DefectDetail detail = new DefectDetail();
            detail.setImageId(imageId);
            detail.setEntityId(matchedEntityId);
            detail.setDefectType(item.getClass_name());
            detail.setConfidence(item.getConfidence());

            // --- 使用 Hutool 序列化 JSON ---
            detail.setBbox(JSONUtil.toJsonStr(item.getBbox()));
            detail.setFeatureVector(JSONUtil.toJsonStr(item.getFeature()));

            detail.setCreateTime(LocalDateTime.now());

            detail.setRoadName("解析中");
            detail.setAddress("解析中");
            detail.setAddressDetail("解析中");

            publisher.publishEvent(new RoadInfoUpdateEvent(imageId, event.getLng(), event.getLat()));

            detailMapper.insert(detail);
        }
    }

    /**
     * AI 处理失败时，将图片记录标记为失败状态并记录错误原因
     */
    @Transactional(rollbackFor = Exception.class)
    public void markAsFailed(Long imageId, String errorMsg) {
        InspectionImage image = imageMapper.selectById(imageId);
        if (image == null) {
            log.error("【数据异常】markAsFailed 找不到图片记录，ID: {}", imageId);
            return;
        }
        image.setStatus("FAILED");
        image.setErrorMsg(errorMsg);
        imageMapper.updateById(image);
        log.warn("【处理失败】图片ID: {} 已标记为失败，原因: {}", imageId, errorMsg);
    }
}