package org.example.roaddetection.service;

import cn.hutool.json.JSONUtil;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.example.roaddetection.dto.AiMatchResponseDTO;
import org.example.roaddetection.dto.TempEntityDTO;
import org.example.roaddetection.events.AiResultEvent;
import org.example.roaddetection.events.DefectDetectedEvent;
import org.example.roaddetection.dto.AiDetectionItem;
import org.example.roaddetection.dto.AiPredictResponse;
import org.example.roaddetection.entity.DefectDetail;
import org.example.roaddetection.entity.InspectionImage;
import org.example.roaddetection.events.RoadInfoUpdateEvent;
import org.example.roaddetection.manager.TaskStateManager;
import org.example.roaddetection.mapper.DefectDetailMapper;
import org.example.roaddetection.mapper.InspectionImageMapper;
import org.example.roaddetection.mapper.InspectionTaskMapper;
import org.example.roaddetection.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.context.event.EventListener;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.io.File;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.*;

@Slf4j
@Service
@RequiredArgsConstructor
public class DroneService {

    private final InspectionImageMapper imageMapper;
    private final DefectDetailMapper detailMapper;
    private final InspectionTaskMapper inspectionTaskMapper;

    private final DroneAsyncService droneAsyncService;
    private final initImageService initImageService;
    private final AiService aiService;

    private final ApplicationEventPublisher publisher;

    private final StringRedisTemplate stringRedisTemplate;

    private final TaskStateManager  taskStateManager;

    @Value("${drone.origin-dir}")
    private String originDir;

    @Value("${drone.root-dir}")
    private String rootDir;

    /**
     * 【主线程同步入口】：处理文件上传、本地保存、数据库初始化占位
     */
    public void processUploadSync(Long taskId, Long droneId,
                                  Double lng, Double lat,
                                  Double altitude, Double yaw, Double pitch, Double roll, Double fov,
                                  MultipartFile file) throws Exception {
        log.info("【图片接收】无人机:{} 坐标:({}, {})", droneId, lng, lat);
        taskStateManager.imageReceived(taskId);
        LocalDateTime now = LocalDateTime.now();

        String originalAbsolutePath = saveOriginalImage(file);
        String originalUrl = PathUtil.extractRelativePath(originalAbsolutePath, "origin/");
        Long imageId = initImageService.initImageRecord(taskId, droneId, lng, lat, originalUrl, now);

        droneAsyncService.processAiAsync(imageId, originalAbsolutePath, taskId, lng, lat, altitude, yaw, pitch, roll, fov);
    }


    /**
     * 监听 AI 处理结果事件
     */
    @Async("siftExecutor")
    @EventListener
    @Transactional(rollbackFor = Exception.class)
    public void onAiResult(AiResultEvent event) {
        try {
            if (event.isSuccess()) {
                saveDetectionResult(event);
            } else {
                markAsFailed(event.getImageId(), event.getErrorMsg());
            }
        } finally {
            taskStateManager.imageProcessed(event.getTaskId());
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
            saveDefectDetails(event);
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
    public void saveDefectDetails(AiResultEvent event) {
        AiPredictResponse aiResult = event.getAiResult();
        if (aiResult.getDetections() == null || aiResult.getDetections().isEmpty()) {
            return;
        }

        InspectionImage lastImage = imageMapper.selectOne(
                new LambdaQueryWrapper<InspectionImage>()
                        .eq(InspectionImage::getTaskId, event.getTaskId())
                        .lt(InspectionImage::getId, event.getImageId())
                        .orderByDesc(InspectionImage::getId)
                        .last("LIMIT 1")
        );

        double[][] H = null;
        List<DefectDetail> previousImageDefects = new ArrayList<>();

        if (lastImage != null) {
            previousImageDefects = detailMapper.selectList(
                    new LambdaQueryWrapper<DefectDetail>()
                            .eq(DefectDetail::getImageId, lastImage.getId())
            );

            File newFile = new File(rootDir + "/" + imageMapper.selectById(event.getImageId()).getOriginalImageUrl());
            File oldFile = new File(rootDir + "/" + lastImage.getOriginalImageUrl());

            if (newFile.exists() && oldFile.exists() && !previousImageDefects.isEmpty()) {
                double imageGap = DistanceUtil.distance(
                        lastImage.getRawLat(), lastImage.getRawLng(),
                        event.getLat(), event.getLng()
                );
                double groundCoverage = 2 * event.getAltitude() * Math.tan(Math.toRadians(event.getFov() / 2));

                if (imageGap < groundCoverage * 0.8) {
                    try {
                        AiMatchResponseDTO matchResult = aiService.match(newFile, oldFile);
                        if (matchResult != null && matchResult.getHomographyMatrix() != null) {
                            H = matchResult.getHomographyMatrix();
                            log.info("成功获取H矩阵");
                        } else {
                            log.warn("【跨帧匹配未命中】...");
                        }
                    } catch (Exception e) {
                        log.error("【跨帧匹配服务异常】: {}", e.getMessage());
                    }
                } else {
                    log.warn("【物理拦截】图片间距 {}m 过大，跳过 ORB 匹配", imageGap);
                }
            }
        }

        Set<String> assignedTempEntityIds = new HashSet<>();
        Set<AiDetectionItem> assignedNewDefects = new HashSet<>();
        List<MatchPair> matchPool = new ArrayList<>();
        if (H != null) {
            for (DefectDetail oldDefect : previousImageDefects) {
                List<Double> oldBbox = BboxUtil.parseBbox(oldDefect.getBbox());
                List<Double> projectedOldBbox = HomographyUtil.projectBbox(oldBbox, H);

                for (AiDetectionItem newDefect : aiResult.getDetections()) {
                    if (!oldDefect.getDefectType().equals(newDefect.getClass_name())) continue;

                    double iou = HomographyUtil.calculateIou(projectedOldBbox, newDefect.getBbox());
                    log.info("交并比：{}",iou);
                    if (iou > 0.3) {
                        matchPool.add(new MatchPair(newDefect, oldDefect, iou));
                    }
                }
            }

            matchPool.sort((p1, p2) -> Double.compare(p2.score, p1.score));

            Map<AiDetectionItem, double[]> newGpsMap = new HashMap<>();
            for (AiDetectionItem item : aiResult.getDetections()) {
                double[] gps = GpsOffsetUtil.calculateRealGps(
                        event.getLng(), event.getLat(), event.getYaw(), event.getPitch(), event.getRoll(),
                        event.getAltitude(), event.getFov(), event.getAiResult().getImageWidth(),
                        event.getAiResult().getImageHeight(), item.getBbox()
                );
                newGpsMap.put(item, gps);
            }

            List<String> tempEntityIds = previousImageDefects.stream()
                    .map(DefectDetail::getTempEntityId)
                    .filter(Objects::nonNull)
                    .distinct()
                    .toList();

            Map<String, TempEntityDTO> tempEntityCache = new HashMap<>();

            if (!tempEntityIds.isEmpty()) {
                // 2. 构造本次任务的 Redis Hash Key
                String redisKey = "TaskTempEntities:" + event.getTaskId();

                // 3. 拉取redis
                List<Object> redisValues =
                        stringRedisTemplate.opsForHash()
                                .multiGet(redisKey, new ArrayList<>(tempEntityIds));

                // 4. 解析 JSON 并放入缓存 Map 中
                for (int i = 0; i < tempEntityIds.size(); i++) {
                    Object jsonStr = redisValues.get(i);
                    if (jsonStr != null) {
                        TempEntityDTO dto = JSONUtil.toBean(jsonStr.toString(), TempEntityDTO.class);
                        tempEntityCache.put(tempEntityIds.get(i), dto);
                    }
                }
            }

            double maxSanityDistance = 8.0;

            for (MatchPair pair : matchPool) {
                if (assignedNewDefects.contains(pair.getNewDefect()) || assignedTempEntityIds.contains(pair.getOldDefect().getTempEntityId())) {
                    continue;
                }

                double[] newGps = newGpsMap.get(pair.getNewDefect());
                TempEntityDTO oldTempEntity = tempEntityCache.get(pair.getOldDefect().getTempEntityId());

                if (oldTempEntity == null) continue;

                // C. 计算两者的物理距离
                double physicalDistance = DistanceUtil.distance(oldTempEntity.getLat(), oldTempEntity.getLng(), newGps[1], newGps[0]);

                // D. 综合判定：IoU 达标 且 物理距离在合理范围内
                if (pair.score >= 0.4 && physicalDistance <= maxSanityDistance) {
                    log.info("【合并成功】实体ID: {}, 距离: {}m, IoU: {}", oldTempEntity.getTempId(), physicalDistance, pair.score);

                    saveSingleDefectDetail(event.getImageId(), pair.getNewDefect(), oldTempEntity.getTempId());

                    oldTempEntity.setLng((oldTempEntity.getLng() + newGps[0]) / 2.0);
                    oldTempEntity.setLat((oldTempEntity.getLat() + newGps[1]) / 2.0);
                    stringRedisTemplate.opsForHash().put(
                            "TaskTempEntities:" + event.getTaskId(),
                            oldTempEntity.getTempId(),
                            JSONUtil.toJsonStr(oldTempEntity)
                    );

                    assignedNewDefects.add(pair.getNewDefect());
                    assignedTempEntityIds.add(oldTempEntity.getTempId());
                } else if (pair.score >= 0.4) {
                    log.warn("【阻断合并】视觉对齐 IoU={}, 但物理距离 {}m 超过限制，判定为误匹配", pair.score, physicalDistance);
                }
            }
        }

        for (AiDetectionItem newDefect : aiResult.getDetections()) {
            if (!assignedNewDefects.contains(newDefect)) {
                handleNewTempEntity(newDefect, event);
            }
        }

        publisher.publishEvent(new RoadInfoUpdateEvent(event.getImageId(), event.getLng(), event.getLat()));
    }


    private void handleNewTempEntity(AiDetectionItem newDefect, AiResultEvent event) {
        // 1. 计算真实的 GPS 坐标
        double[] gps = GpsOffsetUtil.calculateRealGps(
                event.getLng(), event.getLat(), event.getYaw(), event.getPitch(), event.getRoll(), event.getAltitude(), event.getFov(),
                event.getAiResult().getImageWidth(), event.getAiResult().getImageHeight(), newDefect.getBbox());

        double lng = gps[0];
        double lat = gps[1];

        log.info("【发现新病害(暂存Redis)】类型: {}, GPS: ({}, {})", newDefect.getClass_name(), lng, lat);

        // 2. 创建临时实体 DTO
        TempEntityDTO tempDto = new TempEntityDTO(newDefect.getClass_id(), lng, lat);

        // 3. 存入 Redis Hash 缓存
        String redisKey = "TaskTempEntities:" + event.getTaskId();
        stringRedisTemplate.opsForHash().put(redisKey, tempDto.getTempId(), JSONUtil.toJsonStr(tempDto));

        // 4. 将病害详情落库
        saveSingleDefectDetail(event.getImageId(), newDefect,  tempDto.getTempId());
    }

    private void saveSingleDefectDetail(Long imageId, AiDetectionItem item, String tempId) {
        DefectDetail detail = new DefectDetail();
        detail.setImageId(imageId);
        detail.setEntityId(null);
        detail.setTempEntityId(tempId);
        detail.setDefectType(item.getClass_name());
        detail.setConfidence(item.getConfidence());

        detail.setBbox(JSONUtil.toJsonStr(item.getBbox()));
        detail.setFeatureVector(item.getFeature() != null ? JSONUtil.toJsonStr(item.getFeature()) : "{}");

        detail.setCreateTime(LocalDateTime.now());
        detail.setRoadName("解析中");
        detail.setAddress("解析中");
        detail.setAddressDetail("解析中");

        detailMapper.insert(detail);
    }

    /**
     * AI 处理失败时，将图片记录标记为失败状态并记录错误原因
     */
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

    @Data
    private static class MatchPair {
        AiDetectionItem newDefect;
        DefectDetail oldDefect;
        double score;

        public MatchPair(AiDetectionItem item, DefectDetail defectDetail, double score) {
            this.newDefect = item;
            this.oldDefect = defectDetail;
            this.score = score;
        }
    }
}