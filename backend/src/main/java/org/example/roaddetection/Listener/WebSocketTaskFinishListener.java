package org.example.roaddetection.Listener;

import cn.hutool.json.JSONUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.example.roaddetection.events.TaskFinishEvent;
import org.example.roaddetection.handler.DroneWebSocketHandler;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

import java.util.Map;

@Slf4j
@Component
@RequiredArgsConstructor
public class WebSocketTaskFinishListener {
    private final DroneWebSocketHandler webSocketHandler;

    @Async("aiTaskExecutor")
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void onTaskFinished(TaskFinishEvent event) {
        try {
            Map<String, Object> wsMessage = Map.of(
                    "type", "task_status_update",
                    "data", Map.of(
                            "taskId", event.taskId(),
                            "status", event.taskStatus(),  // 2-已完成
                            "droneId", event.droneId(),
                            "droneStatus", event.droneStatus()   // 0-空闲
                    )
            );
            webSocketHandler.broadcastMessage(JSONUtil.toJsonStr(wsMessage));
        } catch (Exception e) {
            log.error("任务结束通知失败", e);
        }
    }
}
