package org.example.roaddetection.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.handlers.JacksonTypeHandler;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

@Data
@TableName(value = "inspection_task", autoResultMap = true)
public class InspectionTask {
    @TableId(type = IdType.AUTO)
    private Long id;

    private String taskName;
    private Long  droneId;

    @TableField(typeHandler = JacksonTypeHandler.class)
    private List<Map<String, Double>> routePoints;
    private Integer status;

    private LocalDateTime createTime;
    private LocalDateTime updateTime;

    private Integer defectCount;
}
