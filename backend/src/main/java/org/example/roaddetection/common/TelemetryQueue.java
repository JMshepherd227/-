package org.example.roaddetection.common;

import org.springframework.stereotype.Component;

import java.util.Map;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.LinkedBlockingQueue;

@Component
public class TelemetryQueue {

    private final BlockingQueue<Map<String, Object>> queue = new LinkedBlockingQueue<>();

    public void produce(Map<String, Object> telemetryData) {
        this.queue.offer(telemetryData);
    }

    public Map<String, Object> consume() throws InterruptedException {
        return this.queue.take();
    }
}
