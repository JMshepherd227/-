package org.example.roaddetection.service;

import cn.hutool.http.HttpRequest;
import cn.hutool.http.HttpResponse;
import cn.hutool.json.JSONUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.example.roaddetection.dto.AiPredictResponse;
import org.example.roaddetection.events.AiResultEvent;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

import java.io.File;

@Slf4j
@Service
@RequiredArgsConstructor
public class DroneAsyncService {

    private final ApplicationEventPublisher publisher;

    @Value("${drone.ai-url:http://localhost:8000/predict/}")
    private String aiUrl;

    @Value("${drone.ai-timeout-ms:10000}")
    private int aiTimeoutMs;

    /**
     * 调用 AI 服务，完成后发布事件，由 DroneService 的监听器处理结果写库。
     */
    @Async("aiTaskExecutor")
    public void processAiAsync(Long imageId, String absolutePath, Long taskId, Double lng, Double lat) {
        log.info("【AI处理开始】图片ID: {}, 本地路径: {}", imageId, absolutePath);

        try {
            File file = new File(absolutePath);
            if (!file.exists()) {
                throw new RuntimeException("找不到已保存的原图文件: " + absolutePath);
            }

            AiPredictResponse aiResult = callAiService(file);

            publisher.publishEvent(new AiResultEvent(this, imageId, taskId, lng, lat, aiResult));
            log.info("【AI处理完成】图片ID: {}, 检测数量: {}", imageId, aiResult.getDetections_num());

        } catch (Exception e) {
            log.error("【AI处理失败】图片ID: {}, 原因: {}", imageId, e.getMessage(), e);
            publisher.publishEvent(new AiResultEvent(this, imageId, e.getMessage()));
        }
    }

    /**
     * 调用 Python AI 服务
     */
    private AiPredictResponse callAiService(File file) {
        HttpResponse response = HttpRequest.post(aiUrl)
                .form("file", file)
                .timeout(aiTimeoutMs)
                .execute();

        if (!response.isOk()) {
            throw new RuntimeException("调用 AI 接口失败, 状态码: " + response.getStatus()
                                       + ", 响应体: " + response.body());
        }

        return JSONUtil.toBean(response.body(), AiPredictResponse.class);
    }
}