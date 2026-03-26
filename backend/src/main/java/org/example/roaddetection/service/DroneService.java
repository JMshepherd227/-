package org.example.roaddetection.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.example.roaddetection.events.AiResultEvent;
import org.example.roaddetection.events.DefectDetectedEvent;
import org.example.roaddetection.dto.AiDetectionItem;
import org.example.roaddetection.dto.AiPredictResponse;
import org.example.roaddetection.entity.DefectDetail;
import org.example.roaddetection.entity.InspectionImage;
import org.example.roaddetection.mapper.DefectDetailMapper;
import org.example.roaddetection.mapper.InspectionImageMapper;
import org.example.roaddetection.mapper.InspectionTaskMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.context.event.EventListener;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.io.File;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.UUID;

@Slf4j
@Service
@RequiredArgsConstructor
public class DroneService {

    private final InspectionImageMapper imageMapper;
    private final DefectDetailMapper detailMapper;
    private final InspectionTaskMapper inspectionTaskMapper;
    private final ApplicationEventPublisher publisher;
    private final DroneAsyncService droneAsyncService;
    private final initImageService initImageService;

    @Value("${drone.origin-dir}")
    private String originDir;

    /**
     * 【主线程同步入口】：处理文件上传、本地保存、数据库初始化占位，
     */
    public void processUploadSync(Long taskId, Long droneId, Double lng, Double lat, MultipartFile file) throws Exception {
        log.info("【图片接收】无人机:{} 坐标:({}, {})", droneId, lng, lat);
        LocalDateTime now = LocalDateTime.now();

        String originalAbsolutePath = saveOriginalImage(file);
        String originalUrl = extractRelativePath(originalAbsolutePath, "origin/");
        Long imageId = initImageService.initImageRecord(taskId, droneId, lng, lat, originalUrl, now);

        droneAsyncService.processAiAsync(imageId, originalAbsolutePath, taskId, lng, lat);
    }


    /**
     * 监听 AI 处理结果事件。
     */
    @Async("aiTaskExecutor")
    @EventListener
    @Transactional(rollbackFor = Exception.class)
    public void onAiResult(AiResultEvent event) {
        if (event.isSuccess()) {
            saveDetectionResult(event.getImageId(), event.getTaskId(),
                    event.getLng(), event.getLat(), event.getAiResult());
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
     * 从绝对路径中提取相对路径
     */
    public String extractRelativePath(String path, String keyword) {
        if (path == null || path.isBlank()) {
            throw new IllegalArgumentException("路径不能为空");
        }
        int index = path.indexOf(keyword);
        if (index == -1) {
            throw new IllegalArgumentException(
                    "路径 [" + path + "] 中未找到关键字 [" + keyword + "]，请检查目录配置是否正确");
        }
        return path.substring(index);
    }

    /**
     * AI 处理成功后，将检测结果写入数据库。
     */
    private void saveDetectionResult(Long imageId, Long taskId, Double lng, Double lat,
                                     AiPredictResponse aiResult) {
        boolean hasDefect = aiResult.getDetections_num() > 0;
        String resultUrl = extractRelativePath(aiResult.getFilePath(), "result/");

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
            saveDefectDetails(imageId, aiResult);
            inspectionTaskMapper.increaseDefectCount(taskId, aiResult.getDetections_num());
            publisher.publishEvent(new DefectDetectedEvent(taskId, lng, lat, aiResult, resultUrl));
            log.info("【检测完成】发现病害 {} 处，图片ID: {}", aiResult.getDetections_num(), imageId);
        } else {
            log.info("【检测通过】该坐标无病害，图片ID: {}", imageId);
        }
    }

    /**
     * 保存病害详情列表
     */
    private void saveDefectDetails(Long imageId, AiPredictResponse aiResult) {
        if (aiResult.getDetections() == null || aiResult.getDetections().isEmpty()) {
            return;
        }
        for (AiDetectionItem item : aiResult.getDetections()) {
            DefectDetail detail = new DefectDetail();
            detail.setImageId(imageId);
            detail.setDefectType(item.getClass_name());
            detail.setConfidence(item.getConfidence());
            detailMapper.insert(detail);
        }
    }

    /**
     * AI 处理失败时，将图片记录标记为失败状态并记录错误原因。
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