package org.example.roaddetection.dto;

import lombok.Data;

@Data
public class DroneUpdateDTO {
    private String droneName;
    private Double lastLng;
    private Double lastLat;
}
