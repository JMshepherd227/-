package org.example.roaddetection.Listener;

import cn.hutool.json.JSONUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.example.roaddetection.events.TelemetryEvent;
import org.example.roaddetection.handler.DroneWebSocketHandler;
import org.springframework.context.event.EventListener;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;

@Slf4j
@Component
@RequiredArgsConstructor
public class TelemetryListener {
    private final DroneWebSocketHandler webSocketHandler;

    @Async("aiTaskExecutor")
    @EventListener
    public void onTelemetryReported(TelemetryEvent event) {
        try {
            Map<String, Object> wsMessage = Map.of(
                    "type", "telemetry",
                    "data", List.of(event.route())
            );

            String jsonStr = JSONUtil.toJsonStr(wsMessage);
            webSocketHandler.broadcastMessage(jsonStr);
        } catch (Exception e) {
            log.error("WebSocket 遥测广播异常", e);
        }
    }
}
