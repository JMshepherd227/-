package org.example.roaddetection.controller;

import lombok.RequiredArgsConstructor;
import org.example.roaddetection.common.Result;
import org.example.roaddetection.dto.DroneUpdateDTO;
import org.example.roaddetection.entity.DroneDevice;
import org.example.roaddetection.mapper.DroneDeviceMapper;
import org.example.roaddetection.mapper.InspectionTaskMapper;
import org.example.roaddetection.service.DeviceService;
import org.springframework.beans.BeanUtils;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/v1/devices")
@RequiredArgsConstructor
public class DroneDeviceController {
    private final DroneDeviceMapper droneDeviceMapper;
    private final DeviceService deviceService;

    /**
     * 添加无人机
     */
    @PostMapping("")
    public Result<DroneDevice> droneUpload(@RequestBody DroneUpdateDTO dto) {
        deviceService.createDrone(dto);
        return Result.success();
    }
    /**
     * 删除无人机
     */
    @DeleteMapping("/{id}")
    public Result<DroneDevice> droneDelete(@PathVariable Long id) {
        deviceService.deleteDrone(id);
        return Result.success();
    }
    /**
     *修改无人机信息
     */
    @PutMapping("/{id}")
    public Result<DroneDevice> droneUpdate(@RequestBody DroneUpdateDTO dto, @PathVariable Long id) {
        deviceService.updateDrone(dto, id);
        return Result.success();
    }
    /**
     *获取无人机信息
     */
    @GetMapping("/{id}")
    public Result<DroneDevice> getDrone(@PathVariable Long id) {
        DroneDevice droneDevice = deviceService.getDrone(id);
        return Result.success(droneDevice);
    }
    /**
     *无人机列表获取
     */
    @GetMapping("")
    public Result<List<DroneDevice>> getDroneList() {
        List<DroneDevice> droneDevices = deviceService.getDroneList();
        return Result.success(droneDevices);
    }
}
