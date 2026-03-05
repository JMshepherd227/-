package org.example.roaddetection.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.socket.config.annotation.EnableWebSocket;
import org.springframework.web.socket.config.annotation.WebSocketConfigurer;
import org.springframework.web.socket.config.annotation.WebSocketHandlerRegistry;

import jakarta.annotation.Resource;

@Configuration
@EnableWebSocket
public class WebSocketConfig implements WebSocketConfigurer {

    @Resource
    private DroneWebSocketHandler droneWebSocketHandler;

    @Override
    public void registerWebSocketHandlers(WebSocketHandlerRegistry registry) {
        registry.addHandler(droneWebSocketHandler, "/ws/telemetry")
                // 【极其重要】允许跨域！因为你的 Vue 通常在 localhost:5173 运行，后端在 8080
                .setAllowedOrigins("*");
    }
}