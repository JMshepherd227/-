package org.example.roaddetection.config;

import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.handler.TextWebSocketHandler;

import java.io.IOException;
import java.util.concurrent.CopyOnWriteArraySet;

@Slf4j
@Component
public class DroneWebSocketHandler extends TextWebSocketHandler {

    // 线程安全的集合，用于存放所有当前连接的 Vue 前端会话
    private static final CopyOnWriteArraySet<WebSocketSession> SESSIONS = new CopyOnWriteArraySet<>();

    /**
     * 当前端 Vue 成功连接到 WebSocket 时触发
     */
    @Override
    public void afterConnectionEstablished(WebSocketSession session) throws Exception {
        SESSIONS.add(session);
        log.info("【WebSocket】有新的前端大屏连接加入！当前总连接数: {}", SESSIONS.size());
    }

    /**
     * 当前端 Vue 断开连接（关闭网页）时触发
     */
    @Override
    public void afterConnectionClosed(WebSocketSession session, CloseStatus status) throws Exception {
        SESSIONS.remove(session);
        log.info("【WebSocket】有前端大屏断开连接。当前总连接数: {}", SESSIONS.size());
    }

    /**
     * 供后端的 Controller 或 Service 调用
     */
    public void broadcastMessage(String jsonMessage) {
        if (SESSIONS.isEmpty()) {
            return;
        }

        TextMessage textMessage = new TextMessage(jsonMessage);
        for (WebSocketSession session : SESSIONS) {
            if (session.isOpen()) {
                try {
                    session.sendMessage(textMessage);
                } catch (IOException e) {
                    log.error("【WebSocket】发送消息失败", e);
                }
            }
        }
    }
}
