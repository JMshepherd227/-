package org.example.roaddetection.dto;

import lombok.Data;
import java.util.List;

@Data
public class AiPredictResponse {
    private String filePath;
    private List<AiDetectionItem> detections;
    private Integer detections_num;
    private String message;
    private Integer imageHeight;
    private Integer imageWidth;
}