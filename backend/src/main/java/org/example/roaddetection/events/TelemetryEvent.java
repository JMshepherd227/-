package org.example.roaddetection.events;

import java.util.Map;

public record TelemetryEvent(Map<String, Object> data) {
}
