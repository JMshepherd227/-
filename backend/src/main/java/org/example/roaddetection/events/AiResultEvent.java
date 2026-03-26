package org.example.roaddetection.events;

import lombok.Getter;
import org.example.roaddetection.dto.AiPredictResponse;
import org.springframework.context.ApplicationEvent;

@Getter
public class AiResultEvent extends ApplicationEvent {

    private final Long imageId;
    private final Long taskId;
    private final Double lng;
    private final Double lat;

    private final AiPredictResponse aiResult;

    private final String errorMsg;

    private final boolean success;

    public AiResultEvent(Object source, Long imageId, Long taskId, Double lng, Double lat, AiPredictResponse aiResult) {
        super(source);
        this.imageId = imageId;
        this.taskId = taskId;
        this.lng = lng;
        this.lat = lat;
        this.aiResult = aiResult;
        this.errorMsg = null;
        this.success = true;
    }

    public AiResultEvent(Object source, Long imageId, String errorMsg) {
        super(source);
        this.imageId = imageId;
        this.taskId = null;
        this.lng = null;
        this.lat = null;
        this.aiResult = null;
        this.errorMsg = errorMsg;
        this.success = false;
    }
}
