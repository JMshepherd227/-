package org.example.roaddetection.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.example.roaddetection.dto.DroneUpdateDTO;
import org.example.roaddetection.entity.DroneDevice;
import org.example.roaddetection.mapper.DroneDeviceMapper;
import org.example.roaddetection.service.DeviceService;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
public class DeviceServiceImpl extends ServiceImpl<DroneDeviceMapper, DroneDevice> implements DeviceService {

    private DroneDeviceMapper droneDeviceMapper;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void createDrone(DroneUpdateDTO dto) {
        DroneDevice droneDevice = new DroneDevice();
        BeanUtils.copyProperties(dto, droneDevice);
        droneDeviceMapper.insert(droneDevice);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void deleteDrone(Long id) {
        if(droneDeviceMapper.selectById(id)==null)
            throw new RuntimeException("无人机不存在");
        else if(droneDeviceMapper.selectById(id).getStatus() == 1)
            throw new RuntimeException("无人机工作中");
        droneDeviceMapper.deleteById(id);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updateDrone(DroneUpdateDTO dto, Long id) {
        if(droneDeviceMapper.selectById(id)==null)
            throw new RuntimeException("无人机不存在");
        else if(droneDeviceMapper.selectById(id).getStatus() == 1)
            throw new RuntimeException("无人机工作中");
        DroneDevice droneDevice = new DroneDevice();
        BeanUtils.copyProperties(dto, droneDevice);
        droneDevice.setId(id);
        droneDeviceMapper.updateById(droneDevice);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public DroneDevice getDrone(Long id) {
        if(droneDeviceMapper.selectById(id)==null)
            throw new RuntimeException("无人机不存在");
        return droneDeviceMapper.selectById(id);
    }

    @Override
    public List<DroneDevice> getDroneList() {
        return droneDeviceMapper.selectList(null);
    }
}
