package org.example.roaddetection.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;
import lombok.AllArgsConstructor;
import lombok.NoArgsConstructor;
import java.util.List;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class GnnMatchRequest {

    @JsonProperty("old_points")
    private List<PointDto> oldPoints;

    @JsonProperty("new_points")
    private List<PointDto> newPoints;

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class PointDto {
        private String id;
        private double x;
        private double y;
        private int type;
    }
}
