package org.example.roaddetection.dto;

import lombok.Data;

import java.util.List;
import java.util.Map;

@Data
public class AiDetectionItem {
    private Integer class_id;
    private String class_name;
    private Double confidence;
    private List<Double> bbox;
    private FeatureDTO feature;
}
