package org.example.roaddetection.dto;

import lombok.Getter;

@Getter
public class TaskQueryDTO {
    private String taskName;
    private Long  droneId;
    private Integer status;
    private Integer defectCount;
    private Integer defectCountMin;
    private Integer defectCountMax;
}
