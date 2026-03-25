package org.example.roaddetection.dto;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import lombok.Data;

import java.time.LocalDateTime;

@Data
public class DroneUpdateDTO {
    private String droneName;
    private Double lastLng;
    private Double lastLat;
}
