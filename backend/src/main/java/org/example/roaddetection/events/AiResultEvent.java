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

    private final Double altitude;
    private final Double yaw;
    private final Double pitch;
    private final Double roll;
    private final Double fov;

    private final AiPredictResponse aiResult;

    private final String errorMsg;

    private final boolean success;

    public AiResultEvent(Object source, Long imageId, Long taskId,
                         Double lng, Double lat, Double altitude, Double yaw, Double pitch, Double roll, Double fov,
                         AiPredictResponse aiResult) {
        super(source);
        this.imageId = imageId;
        this.taskId = taskId;
        this.lng = lng;
        this.lat = lat;
        this.altitude = altitude;
        this.yaw = yaw;
        this.pitch = pitch;
        this.roll = roll;
        this.fov = fov;
        this.aiResult = aiResult;
        this.success = true;
        this.errorMsg = null;
    }

    public AiResultEvent(Object source, Long imageId, String errorMsg) {
        super(source);
        this.imageId = imageId;
        this.taskId = null;
        this.lng = null;
        this.lat = null;
        this.aiResult = null;
        this.altitude = null;
        this.yaw = null;
        this.pitch = null;
        this.roll = null;
        this.fov = null;
        this.errorMsg = errorMsg;
        this.success = false;
    }
}
