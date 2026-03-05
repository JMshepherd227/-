package org.example.roaddetection.controller;

import org.example.roaddetection.config.DroneWebSocketHandler;
import org.example.roaddetection.service.DroneServiceImpl;
import org.springframework.web.bind.annotation.*;
import jakarta.annotation.Resource; // 【注意这里换成 jakarta 了】
import java.util.Map;
import java.util.List;
import cn.hutool.json.JSONUtil;
import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping("/api/v1/drones")
public class TelemetryController {

    @Resource
    private DroneWebSocketHandler webSocketHandler;

    /**
     * 接收 Python 模拟脚本每 100ms 发来的高频位置数据
     */
    @PostMapping("/telemetry")
    public String receiveTelemetry(@RequestBody Map<String, Object> telemetryData) {

        // 1. 把收到的无人机单条位置数据，包装成 WebSocket 规定的数组格式
        // {"type": "telemetry", "data": [{...}]}
        Map<String, Object> wsMessage = Map.of(
                "type", "telemetry",
                "data", List.of(telemetryData) // 放入列表中
        );

        // 2. 将 Map 转换为 JSON 字符串
        String jsonStr = JSONUtil.toJsonStr(wsMessage);

        // 3. 核心大喇叭：通过 WebSocket 瞬间广播给所有打开着的前端网页！
        webSocketHandler.broadcastMessage(jsonStr);

        // 返回给 Python 模拟脚本，表示收到了

        return "{\"code\": 200, \"msg\": \"遥测数据已成功广播\"}";
    }
    @Resource
    private DroneServiceImpl droneService;

    /**
     * 无人机抓拍图片与位置上报 (每 2 秒一次)
     */
    @PostMapping("/upload")
    public String uploadImage(
            @RequestParam("taskId") Long taskId,
            @RequestParam("droneId") Long droneId,
            @RequestParam("lng") Double lng,
            @RequestParam("lat") Double lat,
            @RequestParam("file") MultipartFile file) {

        try {
            // 调用上面写好的超级 Service
            droneService.processUpload(taskId, droneId, lng, lat, file);
            return "{\"code\": 200, \"msg\": \"图片上传与AI处理成功\"}";
        } catch (Exception e) {
            return "{\"code\": 500, \"msg\": \"处理失败: " + e.getMessage() + "\"}";
        }
    }
}


