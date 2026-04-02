package org.example.roaddetection.service;

import com.baomidou.mybatisplus.extension.service.IService;
import org.example.roaddetection.dto.DroneUpdateDTO;
import org.example.roaddetection.entity.DroneDevice;

import java.util.List;

public interface DeviceService extends IService<DroneDevice> {
    void createDrone(DroneUpdateDTO dto);
    void deleteDrone(Long id);
    void updateDrone(DroneUpdateDTO dto, Long id);
    DroneDevice getDrone(Long id);
    List<DroneDevice> getDroneList();
}
