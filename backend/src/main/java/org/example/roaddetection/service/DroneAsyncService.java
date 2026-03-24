package org.example.roaddetection.service;

import jakarta.annotation.Resource;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

@Slf4j
@Service
@RequiredArgsConstructor
public class DroneAsyncService {
    private final DroneService droneService;

    @Async("aiTaskExecutor")
    public void processUploadAsync(Long taskId, Long droneId, Double lng, Double lat, MultipartFile file) {
        try {
            droneService.processUpload(taskId, droneId, lng, lat, file);
        } catch (Exception e) {
            log.error("异步处理失败", e);
        }
    }
}
