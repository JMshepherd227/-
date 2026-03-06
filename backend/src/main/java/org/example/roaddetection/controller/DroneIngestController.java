package org.example.roaddetection.controller;

import org.example.roaddetection.common.TelemetryQueue;
import org.example.roaddetection.service.DroneService;
import org.springframework.web.bind.annotation.*;
import jakarta.annotation.Resource;
import java.util.Map;

import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping("/api/v1/drones")
public class DroneIngestController {

    @Resource
    private TelemetryQueue telemetryQueue;

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
    @Resource
    private DroneService droneService;

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
            droneService.processUploadAsync(taskId, droneId, lng, lat, file);
            return "{\"code\": 200, \"msg\": \"图片上传与AI处理成功\"}";
        } catch (Exception e) {
            return "{\"code\": 500, \"msg\": \"处理失败: " + e.getMessage() + "\"}";
        }
    }
}


