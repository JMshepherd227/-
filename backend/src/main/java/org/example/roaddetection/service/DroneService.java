package org.example.roaddetection.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.example.roaddetection.dto.FeatureDTO;
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
import org.example.roaddetection.util.DistanceUtil;
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
import java.util.*;
import java.util.stream.Collectors;

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

        // 1. 【粗筛】
        double radius = 5.0; // 米

        double deltaLat = radius / 111000.0;
        double deltaLng = radius / (111000.0 * Math.cos(Math.toRadians(event.getLat())));

        List<DefectEntity> nearbyEntities = entityMapper.selectList(
                new LambdaQueryWrapper<DefectEntity>()
                        .between(DefectEntity::getLng, event.getLng() - deltaLng, event.getLng() + deltaLng)
                        .between(DefectEntity::getLat, event.getLat() - deltaLat, event.getLat() + deltaLat)
        );

        List<DefectEntity> filteredEntities = nearbyEntities.stream()
                .filter(e -> DistanceUtil.distance(
                        event.getLat(), event.getLng(),
                        e.getLat(), e.getLng()
                ) <= radius)
                .toList();

        Map<Long, DefectDetail> entityLatestDetailMap = new HashMap<>();
        if (!filteredEntities.isEmpty()) {
            List<Long> entityIds = filteredEntities.stream()
                    .map(DefectEntity::getId)
                    .collect(Collectors.toList());

            List<DefectDetail> recentDetails = detailMapper.selectList(
                    new LambdaQueryWrapper<DefectDetail>()
                            .in(DefectDetail::getEntityId, entityIds)
                            .orderByDesc(DefectDetail::getId)
            );

            for (DefectDetail detail : recentDetails) {
                entityLatestDetailMap.putIfAbsent(detail.getEntityId(), detail);
            }
        }

        // 2. 预处理：计算所有新检测到病害的真实 GPS，封装为上下文对象
        List<NewDefectContext> newDefects = new ArrayList<>();
        for (AiDetectionItem item : aiResult.getDetections()) {
            double[] realGps = GpsOffsetUtil.calculateRealGps(
                    event.getLng(), event.getLat(), event.getYaw(), event.getPitch(), event.getRoll(),
                    event.getAltitude(), event.getFov(), aiResult.getImageWidth(), aiResult.getImageHeight(), item.getBbox()
            );
            newDefects.add(new NewDefectContext(item, realGps[0], realGps[1]));
        }

        // 3. 【核心逻辑：构建得分矩阵字典】计算所有可能的配对得分
        List<MatchPair> matchPool = new ArrayList<>();

        for (NewDefectContext newCtx : newDefects) {
            for (DefectEntity entity : nearbyEntities) {
                // 类别必须一致
                if (!entity.getDefectType().equals(newCtx.item.getClass_name())) continue;

                DefectDetail lastDetail = entityLatestDetailMap.get(entity.getId());
                if (lastDetail == null || lastDetail.getFeatureVector() == null) continue;

                double score = computeMatchScore(newCtx.item, lastDetail);

                // 活跃状态提权：对一直处于监控期的病害放宽匹配容忍度
                if ("ACTIVE".equals(entity.getStatus())) {
                    score = Math.min(score * 1.15, 1.0);
                }

                // 只有基础得分超过 0.5 的才有资格进入候选池，减少排序压力
                if (score > 0.5) {
                    matchPool.add(new MatchPair(newCtx, entity, score));
                }
            }
        }

        // 4. 【贪心匹配】：按得分从高到低排序，确保最高置信度优先绑定，且 1对1 排他
        matchPool.sort((p1, p2) -> Double.compare(p2.score, p1.score));

        Set<Long> assignedEntityIds = new HashSet<>();
        Set<NewDefectContext> assignedNewDefects = new HashSet<>();

        for (MatchPair pair : matchPool) {
            // 如果新病害没被认领，且老病害也没被认领，且得分达标(>= 0.75)
            if (!assignedNewDefects.contains(pair.newCtx)
                && !assignedEntityIds.contains(pair.entity.getId())
                && pair.score >= 0.75) {

                log.info("【高置信匹配】实体ID: {}, 类型: {}, 得分: {}", pair.entity.getId(), pair.entity.getDefectType(), pair.score);

                // 绑定老实体，保存详情记录
                saveSingleDefectDetail(imageId, pair.newCtx.item, pair.entity.getId(), event);

                // 标记为已使用
                assignedNewDefects.add(pair.newCtx);
                assignedEntityIds.add(pair.entity.getId());
            }
        }

        // 5. 处理剩下所有未匹配上的新病害（创建全新的 Entity）
        for (NewDefectContext newCtx : newDefects) {
            if (!assignedNewDefects.contains(newCtx)) {
                log.info("【创建新实体】类型: {}, GPS: ({}, {})", newCtx.item.getClass_name(), newCtx.realLng, newCtx.realLat);

                DefectEntity newEntity = new DefectEntity();
                newEntity.setDefectType(newCtx.item.getClass_name());
                newEntity.setLng(newCtx.realLng);
                newEntity.setLat(newCtx.realLat);
                newEntity.setStatus("ACTIVE");
                newEntity.setCreateTime(LocalDateTime.now());
                entityMapper.insert(newEntity);

                saveSingleDefectDetail(imageId, newCtx.item, newEntity.getId(), event);
            }
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

    /**
     * 提取出的公共保存详情方法
     */
    private void saveSingleDefectDetail(Long imageId, AiDetectionItem item, Long entityId, AiResultEvent event) {
        DefectDetail detail = new DefectDetail();
        detail.setImageId(imageId);
        detail.setEntityId(entityId);
        detail.setDefectType(item.getClass_name());
        detail.setConfidence(item.getConfidence());

        // 序列化坐标和特征
        detail.setBbox(JSONUtil.toJsonStr(item.getBbox()));
        detail.setFeatureVector(JSONUtil.toJsonStr(item.getFeature()));

        detail.setCreateTime(LocalDateTime.now());
        detail.setRoadName("解析中");
        detail.setAddress("解析中");
        detail.setAddressDetail("解析中");

        publisher.publishEvent(new RoadInfoUpdateEvent(imageId, event.getLng(), event.getLat()));
        detailMapper.insert(detail);
    }

    private double computeMatchScore(AiDetectionItem newItem,
                                     DefectDetail lastDetail) {

        String newJson = JSONUtil.toJsonStr(newItem.getFeature());
        String oldJson = lastDetail.getFeatureVector();

        FeatureDTO newBundle = JSONUtil.toBean(newJson, FeatureDTO.class);
        FeatureDTO oldBundle = JSONUtil.toBean(oldJson, FeatureDTO.class);

        // 各维度独立计算相似度
        double simDeep = FeatureUtil.cosineSimilarity(newBundle.getDeep(), oldBundle.getDeep());
        double simLbp  = FeatureUtil.cosineSimilarity(newBundle.getLbp(),  oldBundle.getLbp());
        double rawSimHu   = FeatureUtil.cosineSimilarity(newBundle.getHu(),   oldBundle.getHu());
        double simHu = (rawSimHu + 1.0) / 2.0;
        double areaScore = computeAreaScore(newItem.getBbox(), lastDetail.getBbox());

        return simDeep  * 0.50
               + simLbp   * 0.30
               + areaScore * 0.15
               + simHu    * 0.05;
    }

    private double computeAreaScore(List<Float> newBbox, String oldBboxJson) {
        if (oldBboxJson == null || oldBboxJson.isBlank()) return 0.5;

        List<Float> oldBbox = JSONUtil.toList(oldBboxJson, Float.class);
        if (oldBbox.size() < 4 || newBbox.size() < 4) return 0.5;

        double newArea = (newBbox.get(2) - newBbox.get(0)) * (newBbox.get(3) - newBbox.get(1));
        double oldArea = (oldBbox.get(2) - oldBbox.get(0)) * (oldBbox.get(3) - oldBbox.get(1));

        if (oldArea <= 0 || newArea <= 0) return 0.5;

        double ratio = newArea / oldArea;

        if (ratio >= 0.8 && ratio <= 2.5) {
            return 1.0;
        } else if (ratio > 2.5 && ratio < 5.0) {
            return 1.0 - ((ratio - 2.5) / 2.5) * 0.5;
        } else if (ratio >= 5.0) {
            return 0.0;
        } else if (ratio >= 0.5) {
            return (ratio - 0.5) / 0.3;
        } else {
            return 0.0;
        }
    }

    @Data
    private static class NewDefectContext {
        AiDetectionItem item;
        double realLng;
        double realLat;

        public NewDefectContext(AiDetectionItem item, double realLng, double realLat) {
            this.item = item;
            this.realLng = realLng;
            this.realLat = realLat;
        }
    }

    @Data
    private static class MatchPair {
        NewDefectContext newCtx;
        DefectEntity entity;
        double score;

        public MatchPair(NewDefectContext newCtx, DefectEntity entity, double score) {
            this.newCtx = newCtx;
            this.entity = entity;
            this.score = score;
        }
    }
}