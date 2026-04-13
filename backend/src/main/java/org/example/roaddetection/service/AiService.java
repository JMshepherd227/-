package org.example.roaddetection.service;

import cn.hutool.http.HttpRequest;
import cn.hutool.http.HttpResponse;
import cn.hutool.json.JSONUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.example.roaddetection.dto.AiMatchResponseDTO;
import org.example.roaddetection.dto.AiPredictResponse;
import org.example.roaddetection.dto.GnnMatchRequest;
import org.example.roaddetection.dto.GnnMatchResponse;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.io.File;
import java.util.List;

@Service
@Slf4j
@RequiredArgsConstructor
public class AiService {

    @Value("${drone.ai-url:http://localhost:8000/predict/}")
    private String aiUrl;

    @Value("${drone.match-url:http://localhost:8000/get_homography/}")
    private String matchUrl;

    @Value("${drone.GNN-url:http://localhost:8000/match_points/}")
    private String matchPointUrl;

    @Value("${drone.LoFTR-url:http://localhost:8000/get_homography_loftr/}")
    private String loFTRUrl;

    @Value("${drone.ai-timeout-ms:10000}")
    private int aiTimeoutMs;

    private final RestTemplate restTemplate = new RestTemplate();

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
        return getAiMatchResponseDTO(fileA, fileB, matchUrl);
    }

    /**
     * 调用 Python LoFTR 特征匹配服务
     */
    public AiMatchResponseDTO LoFTRMatch(File fileA, File fileB) {
        return getAiMatchResponseDTO(fileA, fileB, loFTRUrl);
    }

    private AiMatchResponseDTO getAiMatchResponseDTO(File fileA, File fileB, String loFTRUrl) {
        HttpResponse response = HttpRequest.post(loFTRUrl)
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

    /**
     * 调用 Python GNN图神经网络
     */
    public GnnMatchResponse GnnMatcher(List<GnnMatchRequest.PointDto> oldPoints,
                                       List<GnnMatchRequest.PointDto> newPoints) {

        // 1. 构造请求体
        GnnMatchRequest requestBody = new GnnMatchRequest(oldPoints, newPoints);

        // 2. 设置请求头
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        HttpEntity<GnnMatchRequest> requestEntity = new HttpEntity<>(requestBody, headers);

        try {
            // 3. 发起 POST 请求
            log.info("Sending match request to GNN, Old Points: {}, New Points: {}", oldPoints.size(), newPoints.size());
            ResponseEntity<GnnMatchResponse> response = restTemplate.postForEntity(
                    matchPointUrl,
                    requestEntity,
                    GnnMatchResponse.class
            );

            // 4. 解析结果
            if (response.getStatusCode().is2xxSuccessful() && response.getBody() != null) {
                GnnMatchResponse gnnResponse = response.getBody();

                if ("success".equals(gnnResponse.getStatus())) {
                    log.info("GNN匹配成功: {}", gnnResponse);
                    return gnnResponse;
                } else {
                    log.error("GNN匹配错误: {}", gnnResponse.getMessage());
                }
            } else {
                log.error("链接ai服务失败: {}", response.getStatusCode());
            }

        } catch (Exception e) {
            log.error("error: ", e);
        }

        return null;
    }
}
