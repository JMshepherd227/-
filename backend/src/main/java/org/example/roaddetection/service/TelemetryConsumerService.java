package org.example.roaddetection.service;

import cn.hutool.json.JSONUtil;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.example.roaddetection.handler.DroneWebSocketHandler;
import org.example.roaddetection.common.TelemetryQueue;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

@Slf4j
@Service
public class TelemetryConsumerService {
    @Resource
    private DroneWebSocketHandler webSocketHandler;

    @Resource
    private TelemetryQueue telemetryQueue;

    public void startConsuming() {
        Thread consumerThread = new Thread(() -> {
            log.info("遥测数据广播消费者线程已启动...");
            while (!Thread.currentThread().isInterrupted()) {
                try {
                    Map<String, Object> telemetryData = telemetryQueue.consume();
                    Map<String, Object> wsMessage = Map.of(
                            "type", "telemetry",
                            "data", List.of(telemetryData)
                    );
                    String jsonStr = JSONUtil.toJsonStr(wsMessage);
                    webSocketHandler.broadcastMessage(jsonStr);

                } catch (InterruptedException e) {
                    log.warn("遥测广播消费者线程被中断。");
                    Thread.currentThread().interrupt();
                } catch (Exception e) {
                    log.error("处理遥测数据时发生未知异常", e);
                }
            }
        });

        consumerThread.setName("telemetry-consumer");
        consumerThread.setDaemon(true);
        consumerThread.start();
    }
}
