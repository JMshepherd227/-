package org.example.roaddetection.service;

import com.baomidou.mybatisplus.extension.service.IService;
import org.example.roaddetection.entity.InspectionTask;

public interface InspectionTaskService extends IService<InspectionTask> {
    void finishTaskByDrone(Long droneId);
}
