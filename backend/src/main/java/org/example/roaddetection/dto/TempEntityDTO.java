package org.example.roaddetection.dto;

import lombok.Data;

import java.util.UUID;

@Data
public class TempEntityDTO {
    private String tempId;
    private int defectType;
    private Double Lng;
    private Double Lat;

    public TempEntityDTO(int defectType, Double lng, Double lat) {
        this.tempId = UUID.randomUUID().toString().replace("-", "");
        this.defectType = defectType;
        this.Lng = lng;
        this.Lat = lat;
    }
}
