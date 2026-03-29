package org.example.roaddetection.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("inspection_image")
public class InspectionImage {
    @TableId(type = IdType.AUTO)
    private Long id;

    private Long taskId;
    private Long droneId;

    private String originalImageUrl;
    private String resultImageUrl;

    private Double rawLng;
    private Double rawLat;

    private Double matchedLng;
    private Double matchedLat;

    @TableField("is_defect")
    private Integer isDefect;
    private Integer defectCount;

    private LocalDateTime captureTime;
    private LocalDateTime createTime;

    private String status;
    private String errorMsg;
}
