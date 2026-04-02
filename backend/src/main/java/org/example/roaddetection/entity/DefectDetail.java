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
    private Long entityId;
    private String defectType;
    private Double confidence;
    private String bbox;
    private String featureVector;
    private LocalDateTime createTime;
    private String roadName;
    private String address;
    private String addressDetail;
    @TableField(exist = false)
    private String resultImageUrl; // 画了框的结果图
    @TableField(exist = false)
    private String originalImageUrl; // 原图
    @TableField(exist = false)
    private LocalDateTime captureTime; // 拍摄时间
}
