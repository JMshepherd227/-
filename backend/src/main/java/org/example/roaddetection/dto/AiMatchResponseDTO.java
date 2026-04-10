package org.example.roaddetection.dto;

import lombok.Data;

@Data
public class AiMatchResponseDTO {
    private String status;
    private String message;
    private int inliers;
    private double processingTimeMs;
    private double[][] homographyMatrix;
}
