package org.example.roaddetection.events;

import org.example.roaddetection.dto.AiPredictResponse;

public record DefectDetectedEvent(Long taskId, Double lng, Double lat, AiPredictResponse aiPredictResponse, String imageUrl) {
}
