package org.example.roaddetection.events;

public record TaskFinishEvent(Long taskId, Integer taskStatus, Long droneId, Integer droneStatus) {
}
