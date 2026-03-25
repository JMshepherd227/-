package org.example.roaddetection.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.example.roaddetection.entity.DroneDevice;
import org.example.roaddetection.entity.InspectionTask;
import org.example.roaddetection.enums.DroneStatus;
import org.example.roaddetection.enums.TaskStatus;
import org.example.roaddetection.events.TaskFinishEvent;
import org.example.roaddetection.mapper.DroneDeviceMapper;
import org.example.roaddetection.mapper.InspectionTaskMapper;
import org.example.roaddetection.service.InspectionTaskService;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Slf4j
@Service
@RequiredArgsConstructor
public class InspectionTaskServiceImpl extends ServiceImpl<InspectionTaskMapper, InspectionTask> implements InspectionTaskService {

    private final DroneDeviceMapper droneDeviceMapper;
    private final ApplicationEventPublisher publisher;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void finishTaskByDrone(Long droneId) {
        InspectionTask task = baseMapper.selectOne(new LambdaQueryWrapper<InspectionTask>()
                .eq(InspectionTask::getDroneId, droneId)
                .eq(InspectionTask::getStatus, TaskStatus.RUNNING.getValue()));

        if (task == null) {
            throw new RuntimeException("该无人机当前没有正在执行的任务");
        }

        DroneDevice drone = droneDeviceMapper.selectById(droneId);
        if (drone == null) {
            throw new RuntimeException("无人机设备不存在");
        }

        task.setStatus(TaskStatus.FINISHED.getValue());
        drone.setStatus(DroneStatus.WAITING.getValue());

        baseMapper.updateById(task);
        droneDeviceMapper.updateById(drone);

        publisher.publishEvent(new TaskFinishEvent(
                task.getId(),
                task.getStatus(),
                droneId,
                drone.getStatus()
        ));

        log.info("任务已成功结束：TaskID={}, DroneID={}", task.getId(), droneId);
    }
}
