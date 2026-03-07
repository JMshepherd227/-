package org.example.roaddetection.service;

import cn.hutool.http.HttpRequest;
import cn.hutool.http.HttpResponse;
import cn.hutool.json.JSONUtil;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.example.roaddetection.common.DroneWebSocketHandler;
import org.example.roaddetection.dto.AiDetectionItem;
import org.example.roaddetection.dto.AiPredictResponse;
import org.example.roaddetection.entity.DefectDetail;
import org.example.roaddetection.entity.InspectionImage;
import org.example.roaddetection.mapper.DefectDetailMapper;
import org.example.roaddetection.mapper.InspectionImageMapper;
import org.example.roaddetection.mapper.InspectionTaskMapper;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.io.File;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.Map;
import java.util.UUID;

@Slf4j
@Service
public class DroneService {

    @Resource
    private InspectionImageMapper imageMapper;

    @Resource
    private DefectDetailMapper detailMapper;

    @Resource
    private DroneWebSocketHandler webSocketHandler;

    @Resource
    private InspectionTaskMapper inspectionTaskMapper;

    /** Python AI 接口 */
    private static final String AI_URL = "http://localhost:8000/predict/";

    /** 原图保存目录 */
    private static final String ORIGIN_DIR = "D:/work(work only)/python/UAVRoadDetection/origin";

    /**
     * 处理无人机上传图片
     */
    @Transactional(rollbackFor = Exception.class)
    public void processUpload(Long taskId, Long droneId, Double lng, Double lat, MultipartFile file) throws Exception {

        log.info("【图片接收】无人机:{} 坐标:({}, {})", droneId, lng, lat);

        LocalDateTime now = LocalDateTime.now();

        // 1. 调用 AI
        AiPredictResponse aiResult = callAiService(file);

        // 2. 保存原始图片
        String originalAbsolutePath = saveOriginalImage(file);

        // 3. 解析 AI 结果
        boolean hasDefect = aiResult.getDetections_num() > 0;

        String resultUrl = extractRelativePath(aiResult.getFilePath(), "result/");
        String originalUrl = extractRelativePath(originalAbsolutePath, "origin/");

        // 4. 保存图片记录
        InspectionImage imageRecord = saveImageRecord(
                taskId, droneId, lng, lat,
                resultUrl, originalUrl,
                hasDefect, aiResult.getDetections_num(),
                now
        );

        // 5. 保存病害详情 + 通知前端
        if (hasDefect) {
            saveDefectDetails(imageRecord.getId(), aiResult);
            notifyFrontend(taskId, lng, lat, aiResult, resultUrl);
            inspectionTaskMapper.increaseDefectCount(taskId, aiResult.getDetections_num());
        } else {
            log.info("【检测通过】该坐标无病害");
        }
    }

    /**
     * 调用 Python AI 服务
     */
    private AiPredictResponse callAiService(MultipartFile file) throws Exception {

        HttpResponse response = HttpRequest.post(AI_URL)
                .form("file", file.getBytes(), file.getOriginalFilename())
                .timeout(10000)
                .execute();

        if (!response.isOk()) {
            throw new RuntimeException("调用 AI 接口失败: " + response.getStatus());
        }

        return JSONUtil.toBean(response.body(), AiPredictResponse.class);
    }

    /**
     * 保存原始图片
     */
    private String saveOriginalImage(MultipartFile file) throws Exception {

        String date = LocalDate.now().toString();
        String fileName = UUID.randomUUID().toString().substring(0, 8) + ".jpg";

        String saveDir = ORIGIN_DIR + "/" + date;

        File dir = new File(saveDir);
        if (!dir.exists()) {
            dir.mkdirs();
        }

        String absolutePath = saveDir + "/" + fileName;

        file.transferTo(new File(absolutePath));

        return absolutePath;
    }

    /**
     * 提取相对路径
     */
    private String extractRelativePath(String path, String keyword) {
        return path.substring(path.indexOf(keyword));
    }

    /**
     * 保存图片记录
     */
    private InspectionImage saveImageRecord(
            Long taskId,
            Long droneId,
            Double lng,
            Double lat,
            String resultUrl,
            String originalUrl,
            boolean hasDefect,
            int defectCount,
            LocalDateTime captureTime) {

        InspectionImage image = new InspectionImage();

        image.setTaskId(taskId);
        image.setDroneId(droneId);

        image.setRawLng(lng);
        image.setRawLat(lat);

        image.setMatchedLng(lng);
        image.setMatchedLat(lat);

        image.setResultImageUrl(resultUrl);
        image.setOriginalImageUrl(originalUrl);

        image.setIsDefect(hasDefect ? 1 : 0);
        image.setDefectCount(defectCount);

        image.setCaptureTime(captureTime);

        imageMapper.insert(image);

        return image;
    }

    /**
     * 保存病害详情
     */
    private void saveDefectDetails(Long imageId, AiPredictResponse aiResult) {

        for (AiDetectionItem item : aiResult.getDetections()) {

            DefectDetail detail = new DefectDetail();

            detail.setImageId(imageId);
            detail.setDefectType(item.getClass_name());
            detail.setConfidence(item.getConfidence());

            detailMapper.insert(detail);
        }
    }

    /**
     * WebSocket 通知前端
     */
    private void notifyFrontend(Long taskId, Double lng, Double lat, AiPredictResponse aiResult, String imageUrl) {

        String defectType = aiResult.getDetections().get(0).getClass_name();

        Map<String, Object> wsMessage = Map.of(
                "type", "new_defect",
                "data", Map.of(
                        "taskId", taskId,
                        "lng", lng,
                        "lat", lat,
                        "defectType", defectType,
                        "imageUrl", "http://localhost:8080/" + imageUrl
                )
        );

        webSocketHandler.broadcastMessage(JSONUtil.toJsonStr(wsMessage));

        log.warn("【发现病害】坐标({}, {}) 类型: {}", lng, lat, defectType);
    }
}
