package org.example.roaddetection.dto;

import lombok.Data;
import java.util.List;

@Data
public class AiDetectionItem {
    private Integer class_id;
    private String class_name;
    private Double confidence;
}
