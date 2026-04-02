package org.example.roaddetection.Listener;

import cn.hutool.json.JSONUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.example.roaddetection.events.DefectDetectedEvent;
import org.example.roaddetection.handler.DroneWebSocketHandler;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

import java.util.Map;

@Slf4j
@Component
@RequiredArgsConstructor
public class WebSocketAlertListener {
    private final DroneWebSocketHandler webSocketHandler;

    @Async("aiTaskExecutor")
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void onDefectDetected(DefectDetectedEvent event) {
        log.info("监听到病害事件，准备推送WebSocket报警...");

        try {
            Map<String, Object> wsMessage = Map.of(
                    "type", "new_defect",
                    "data", Map.of(
                            "taskId", event.taskId(),
                            "lng", event.lng(),
                            "lat", event.lat(),
                            "detail", event.aiPredictResponse(),
                            "imageUrl", "http://localhost:8080/" + event.imageUrl()
                    )
            );

            webSocketHandler.broadcastMessage(JSONUtil.toJsonStr(wsMessage));

            log.warn("【实时报警已推送】任务:{} 坐标:({},{})",
                    event.taskId(), event.lng(), event.lat());
        } catch (Exception e) {
            log.error("推送病害报警失败:{} 任务:{} 完整响应:{}", e, event.taskId(), event.aiPredictResponse());
        }
    }
}
