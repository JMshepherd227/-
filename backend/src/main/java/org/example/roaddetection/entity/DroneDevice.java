package org.example.roaddetection.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("drone_device")
public class DroneDevice {
    @TableId(type = IdType.AUTO)
    private Long id;

    private String droneName;
    private Integer status;

    private Double lastLng;
    private Double lastLat;

    private LocalDateTime createTime;
    private LocalDateTime updateTime;
}
