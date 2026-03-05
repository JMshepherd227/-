package org.example.roaddetection.entity;

import cn.hutool.json.JSON;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("inspection_task")
public class InspectionTask {
    @TableId(type = IdType.AUTO)
    private Long id;

    private String taskName;
    private Long  droneId;

    private JSON routePoints;
    private Integer status;

    private LocalDateTime createTime;
    private LocalDateTime updateTime;
}
