package org.example.roaddetection.controller;

import org.example.roaddetection.config.DroneWebSocketHandler;
import org.example.roaddetection.service.DroneService;
import org.springframework.web.bind.annotation.*;
import jakarta.annotation.Resource;
import java.util.Map;
import java.util.List;
import cn.hutool.json.JSONUtil;
import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping("/api/v1/drones")
public class DroneIngestController {

    @Resource
    private DroneWebSocketHandler webSocketHandler;

    /**
     * 无人机位置上报
     */
    @PostMapping("/telemetry")
    public String receiveTelemetry(@RequestBody Map<String, Object> telemetryData) {

        // 1. 接收无人机单条位置数据，包装成 WebSocket 规定的数组格式
        // {"type": "telemetry", "data": [{...}]}
        Map<String, Object> wsMessage = Map.of(
                "type", "telemetry",
                "data", List.of(telemetryData)
        );

        String jsonStr = JSONUtil.toJsonStr(wsMessage);

        webSocketHandler.broadcastMessage(jsonStr);

        return "{\"code\": 200, \"msg\": \"遥测数据已成功广播\"}";
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
            droneService.processUpload(taskId, droneId, lng, lat, file);
            return "{\"code\": 200, \"msg\": \"图片上传与AI处理成功\"}";
        } catch (Exception e) {
            return "{\"code\": 500, \"msg\": \"处理失败: " + e.getMessage() + "\"}";
        }
    }
}


