package org.example.roaddetection.dto;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.extension.handlers.JacksonTypeHandler;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

@Data
public class TaskUpdateDTO {
    private String taskName;
    private Long  droneId;

    @TableField(typeHandler = JacksonTypeHandler.class)
    private List<Map<String, Double>> routePoints;
    private Integer status;

    private Integer defectCount;
}
