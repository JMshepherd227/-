package org.example.roaddetection.service;

import cn.hutool.json.JSONUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.example.roaddetection.events.TelemetryEvent;
import org.example.roaddetection.handler.DroneWebSocketHandler;
import org.springframework.context.event.EventListener;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

@Slf4j
@Service
@RequiredArgsConstructor
public class TelemetryConsumerService {

    private final DroneWebSocketHandler webSocketHandler;

    @Async("aiTaskExecutor")
    @EventListener
    public void handleTelemetryEvent(TelemetryEvent event) {
        try {
            log.info("监听到遥测数据事件，准备广播...");

            Map<String, Object> wsMessage = Map.of(
                    "type", "telemetry",
                    "data", List.of(event.data())
            );

            String jsonStr = JSONUtil.toJsonStr(wsMessage);
            webSocketHandler.broadcastMessage(jsonStr);

        } catch (Exception e) {
            log.error("广播遥测数据时发生错误", e);
        }
    }
}
