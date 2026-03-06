package org.example.roaddetection.common;

import lombok.Getter;

@Getter
public class TileBBox {
    public double minLat;
    public double maxLat;
    public double minLng;
    public double maxLng;

    public TileBBox(double minLat, double maxLat, double minLng, double maxLng) {
        this.minLat = minLat;
        this.maxLat = maxLat;
        this.minLng = minLng;
        this.maxLng = maxLng;
    }
}
