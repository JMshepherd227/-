package org.example.roaddetection.service;

import com.baomidou.mybatisplus.extension.service.IService;
import org.example.roaddetection.dto.TaskQueryDTO;
import org.example.roaddetection.dto.TaskUpdateDTO;
import org.example.roaddetection.entity.InspectionTask;

import java.util.List;

public interface InspectionTaskService extends IService<InspectionTask> {
    void finishTaskByDrone(Long droneId);
    void startTaskByID(Long taskId);
    InspectionTask getTask(Long taskId);
    List<InspectionTask> searchTasks(TaskQueryDTO dto);
    void createTask(TaskUpdateDTO dto);
    void updateTask(TaskUpdateDTO dto,  Long taskId);
    void deleteTask(Long taskId);
}
