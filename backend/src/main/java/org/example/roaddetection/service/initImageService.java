package org.example.roaddetection.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.example.roaddetection.entity.InspectionImage;
import org.example.roaddetection.mapper.InspectionImageMapper;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

@Slf4j
@Service
@RequiredArgsConstructor
public class initImageService {
    private final InspectionImageMapper imageMapper;

    @Transactional(rollbackFor = Exception.class)
    public Long initImageRecord(Long taskId, Long droneId, Double lng, Double lat,
                                String originalUrl, LocalDateTime captureTime) {
        InspectionImage image = new InspectionImage();
        image.setTaskId(taskId);
        image.setDroneId(droneId);
        image.setRawLng(lng);
        image.setRawLat(lat);
        image.setMatchedLng(lng);
        image.setMatchedLat(lat);
        image.setOriginalImageUrl(originalUrl);
        image.setCaptureTime(captureTime);
        image.setStatus("PROCESSING");

        imageMapper.insert(image);
        log.info("【数据库初始化】图片记录已创建，ID: {}", image.getId());
        return image.getId();
    }
}
