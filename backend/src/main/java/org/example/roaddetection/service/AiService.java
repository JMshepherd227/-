package org.example.roaddetection.service;

import cn.hutool.http.HttpRequest;
import cn.hutool.http.HttpResponse;
import cn.hutool.json.JSONUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.example.roaddetection.dto.AiMatchResponseDTO;
import org.example.roaddetection.dto.AiPredictResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.File;

@Service
@Slf4j
@RequiredArgsConstructor
public class AiService {

    @Value("${drone.ai-url:http://localhost:8000/predict/}")
    private String aiUrl;

    @Value("${drone.match-url:http://localhost:8000/get_homography/}")
    private String matchUrl;

    @Value("${drone.ai-timeout-ms:10000}")
    private int aiTimeoutMs;

    /**
     * 调用 Python AI 服务
     */
    public AiPredictResponse predict(File file) {
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

    /**
     * 调用 Python 特征匹配服务
     */
    public AiMatchResponseDTO match(File fileA, File fileB) {
        HttpResponse response = HttpRequest.post(matchUrl)
                .form("file1", fileA)
                .form("file2", fileB)
                .timeout(aiTimeoutMs)
                .execute();

        if (!response.isOk()) {
            throw new RuntimeException("调用 AI 接口失败, 状态码: " + response.getStatus()
                                       + ", 响应体: " + response.body());
        }

        return JSONUtil.toBean(response.body(), AiMatchResponseDTO.class);
    }
}
