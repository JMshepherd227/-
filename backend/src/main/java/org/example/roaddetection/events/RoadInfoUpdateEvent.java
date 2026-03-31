package org.example.roaddetection.events;

public record RoadInfoUpdateEvent(Long imageId, Double lng, Double lat) {
}
