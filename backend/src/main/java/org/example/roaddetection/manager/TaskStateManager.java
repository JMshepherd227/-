package org.example.roaddetection.manager;

import lombok.Data;
import lombok.extern.slf4j.Slf4j;
import org.example.roaddetection.service.GlobalMatchService;
import org.springframework.context.annotation.Lazy;
import org.springframework.stereotype.Component;

import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

@Slf4j
@Component
public class TaskStateManager {

    // 使用 Lazy 注入，避免与 GlobalMatchService 产生循环依赖
    private final GlobalMatchService globalMatchService;

    // 存储每个 Task 的并发状态
    private final ConcurrentHashMap<Long, TaskState> taskStateMap = new ConcurrentHashMap<>();

    public TaskStateManager(@Lazy GlobalMatchService globalMatchService) {
        this.globalMatchService = globalMatchService;
    }

    @Data
    private static class TaskState {
        // 正在整个 AI 管线（YOLO + SIFT）中流转的图片数量
        AtomicInteger pendingImages = new AtomicInteger(0);
        volatile boolean isFinishSignalReceived = false;
        volatile boolean isGnnTriggered = false;
    }

    private TaskState getTaskState(Long taskId) {
        return taskStateMap.computeIfAbsent(taskId, k -> new TaskState());
    }

    /**
     * 1. 接收到图片时调用：积压数 +1
     */
    public void imageReceived(Long taskId) {
        getTaskState(taskId).getPendingImages().incrementAndGet();
        log.debug("Task {} 接收新图片，当前积压: {}", taskId, getTaskState(taskId).getPendingImages().get());
    }

    /**
     * 2. YOLO 和 SIFT 全部处理完毕时调用：积压数 -1
     */
    public void imageProcessed(Long taskId) {
        TaskState state = getTaskState(taskId);
        int remain = state.getPendingImages().decrementAndGet();
        log.debug("Task {} 处理完一张图片，当前积压: {}", taskId, remain);
        checkAndTriggerGnn(taskId, state);
    }

    /**
     * 3. 收到外部任务结束指令时调用
     */
    public void receiveFinishSignal(Long taskId) {
        TaskState state = getTaskState(taskId);
        state.setFinishSignalReceived(true);
        log.info("Task {} 收到结束信号！", taskId);
        checkAndTriggerGnn(taskId, state);
    }

    /**
     * 核心校验逻辑：双重屏障
     */
    private void checkAndTriggerGnn(Long taskId, TaskState state) {
        // 加锁，防止多线程同时满足条件时重复触发 GNN
        synchronized (state) {
            if (state.isGnnTriggered()) {
                return;
            }
            // 触发门槛：收到结束信号 && 积压任务为 0
            if (state.isFinishSignalReceived() && state.getPendingImages().get() == 0) {
                state.setGnnTriggered(true);
                log.info("🎯 Task {} 屏障解除 (信号=true, 积压=0)，触发 GNN 全局对齐！", taskId);

                // 触发 GNN 异步执行
                globalMatchService.executeGlobalMatch(taskId);

                // 清理内存，防止内存泄漏
                taskStateMap.remove(taskId);
            }
        }
    }
}
