package org.example.roaddetection.dto;

import lombok.Data;

import java.util.List;

@Data
public class FeatureDTO {
    private List<Float> deep;
    private List<Float> hu;
    private List<Float> lbp;
}
