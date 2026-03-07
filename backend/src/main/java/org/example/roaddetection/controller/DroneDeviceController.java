package org.example.roaddetection.controller;

import jakarta.annotation.Resource;
import org.example.roaddetection.common.Result;
import org.example.roaddetection.entity.DroneDevice;
import org.example.roaddetection.mapper.DroneDeviceMapper;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/v1/devices")
public class DroneDeviceController {

    @Resource
    private DroneDeviceMapper droneDeviceMapper;

    /**
     * 添加无人机
     */
    @PostMapping("")
    public Result<DroneDevice> droneUpload(@RequestBody DroneDevice droneDevice) {
        try {
            droneDeviceMapper.insert(droneDevice);
            return Result.success();
        } catch (Exception e) {
            return Result.fail("添加失败" + e.getMessage());
        }
    }
    /**
     * 删除无人机
     */
    @DeleteMapping("/{id}")
    public Result<DroneDevice> droneDelete(@PathVariable Long id) {
        try {
            if(droneDeviceMapper.selectById(id)==null)
                return Result.fail("id不存在");
            if(droneDeviceMapper.selectById(id).getStatus() == 1)
                return Result.fail("无人机工作中");
            droneDeviceMapper.deleteById(id);
            return Result.success();
        } catch (Exception e) {
            return Result.fail("删除失败" + e.getMessage());
        }
    }
    /**
     *修改无人机信息
     */
    @PutMapping("/{id}")
    public Result<DroneDevice> droneUpdate(@RequestBody DroneDevice droneDevice, @PathVariable Long id) {
        try {
            if(droneDeviceMapper.selectById(id)==null)
                return Result.fail("id不存在");
            droneDevice.setId(id);
            droneDeviceMapper.updateById(droneDevice);
            return Result.success();
        } catch (Exception e) {
            return Result.fail("修改失败" + e.getMessage());
        }
    }
    /**
     *获取无人机信息
     */
    @GetMapping("/{id}")
    public Result<DroneDevice> getDrone(@PathVariable Long id) {
        try {
            if(droneDeviceMapper.selectById(id)==null)
                return Result.fail("id不存在");
            DroneDevice droneDevice = droneDeviceMapper.selectById(id);
            return Result.success(droneDevice);
        } catch (Exception e) {
            return Result.fail("修改失败" + e.getMessage());
        }
    }
    /**
     *无人机列表获取
     */
    @GetMapping("")
    public Result<List<DroneDevice>> getDroneList() {
        try {
            List<DroneDevice> droneDevices = droneDeviceMapper.selectList(null);
            return Result.success(droneDevices);
        } catch (Exception e) {
            return Result.fail("获取失败：" + e.getMessage());
        }
    }
}
