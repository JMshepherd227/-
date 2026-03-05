package org.example.roaddetection.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("defect_detail")
public class DefectDetail {
    @TableId(type = IdType.AUTO)
    private Long id;
    private Long imageId;
    private String defectType;
    private Double confidence;
    private LocalDateTime createTime;

    @TableField(exist = false)
    private LocalDateTime updateTime;
}
