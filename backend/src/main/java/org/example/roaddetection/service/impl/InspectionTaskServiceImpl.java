package org.example.roaddetection.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.example.roaddetection.dto.TaskQueryDTO;
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

import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
public class InspectionTaskServiceImpl extends ServiceImpl<InspectionTaskMapper, InspectionTask> implements InspectionTaskService {

    private final DroneDeviceMapper droneDeviceMapper;
    private final ApplicationEventPublisher publisher;
    private final InspectionTaskMapper inspectionTaskMapper;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void finishTaskByDrone(Long droneId) {
        List<InspectionTask> tasks = baseMapper.selectList(new LambdaQueryWrapper<InspectionTask>()
                .eq(InspectionTask::getDroneId, droneId)
                .eq(InspectionTask::getStatus, TaskStatus.RUNNING.getValue()));

        InspectionTask task;

        if (tasks.isEmpty()) {
            throw new RuntimeException("该无人机当前没有正在执行的任务");
        } else if (tasks.size() > 1) {
            throw new RuntimeException("该无人机当前有多个正在执行中的任务");
        } else {
            task = tasks.get(0);
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

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void startTaskByID(Long taskId) {
        InspectionTask task = inspectionTaskMapper.selectById(taskId);
        if (task == null)
            throw new RuntimeException("任务不存在");
        if (task.getStatus() != 0)
            throw new RuntimeException("任务非未开始状态");

        DroneDevice drone = droneDeviceMapper.selectById(task.getDroneId());
        if (drone == null)
            throw new RuntimeException("无人机不存在");
        if (drone.getStatus() != 0) {
            throw new RuntimeException("无人机 " + drone.getDroneName() + " 正在执行其他任务，请先结束该任务");
        }

        task.setStatus(1);
        drone.setStatus(1);

        inspectionTaskMapper.updateById(task);
        droneDeviceMapper.updateById(drone);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public InspectionTask getTask(Long taskId) {
        InspectionTask task = inspectionTaskMapper.selectById(taskId);
        if(task==null)
            throw new RuntimeException("任务不存在");
        return task;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public List<InspectionTask> searchTasks(TaskQueryDTO query) {
        LambdaQueryWrapper<InspectionTask> wrapper = new LambdaQueryWrapper<>();

        wrapper.like(query.getTaskName()!=null,
                InspectionTask::getTaskName,
                query.getTaskName());
        wrapper.eq(query.getDroneId()!=null,
                InspectionTask::getDroneId,
                query.getDroneId());
        wrapper.eq(query.getStatus()!=null,
                InspectionTask::getStatus,
                query.getStatus());
        wrapper.eq(query.getDefectCount()!=null,
                InspectionTask::getDefectCount,
                query.getDefectCount());
        wrapper.ge(query.getDefectCountMin()!=null,
                InspectionTask::getDefectCount,
                query.getDefectCountMin());
        wrapper.le(query.getDefectCountMax()!=null,
                InspectionTask::getDefectCount,
                query.getDefectCountMax());

        return inspectionTaskMapper.selectList(wrapper);
    }
}
