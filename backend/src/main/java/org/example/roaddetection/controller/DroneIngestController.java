package org.example.roaddetection.controller;

import lombok.RequiredArgsConstructor;
import org.example.roaddetection.common.TelemetryQueue;
import org.example.roaddetection.service.DroneAsyncService;
import org.springframework.web.bind.annotation.*;
import java.util.Map;

import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping("/api/v1/drones")
@RequiredArgsConstructor
public class DroneIngestController {
    private final TelemetryQueue telemetryQueue;
    private final DroneAsyncService  droneAsyncService;

    /**
     * 无人机位置上报
     */
    @PostMapping("/telemetry")
    public String receiveTelemetry(@RequestBody Map<String, Object> telemetryData) {
        try{
            telemetryQueue.produce(telemetryData);
            return "{\"code\": 200, \"msg\": \"遥测数据已成功广播\"}";
        } catch (Exception e){
            return "{\"code\": 500, \"msg\": \"广播失败: " + e.getMessage() + "\"}";
        }

    }

    /**
     * 无人机抓拍图片与位置上报
     */
    @PostMapping("/upload")
    public String uploadImage(
            @RequestParam("taskId") Long taskId,
            @RequestParam("droneId") Long droneId,
            @RequestParam("lng") Double lng,
            @RequestParam("lat") Double lat,
            @RequestParam("file") MultipartFile file) {

        try {
            droneAsyncService.processUploadAsync(taskId, droneId, lng, lat, file);
            return "{\"code\": 200, \"msg\": \"图片上传与AI处理成功\"}";
        } catch (Exception e) {
            return "{\"code\": 500, \"msg\": \"处理失败: " + e.getMessage() + "\"}";
        }
    }
}


