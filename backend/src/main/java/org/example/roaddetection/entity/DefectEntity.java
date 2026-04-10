package org.example.roaddetection.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("defect_entity")
public class DefectEntity {
    @TableId(type = IdType.AUTO)
    private Long id;
    private int defectType;
    private Double lng;
    private Double lat;
    private String status;
    private LocalDateTime createTime;
}
