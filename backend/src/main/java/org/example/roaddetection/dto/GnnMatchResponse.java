package org.example.roaddetection.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;
import java.util.List;

@Data
public class GnnMatchResponse {

    private String status;
    private String message;
    private List<MatchResultItem> results;

    @Data
    public static class MatchResultItem {
        @JsonProperty("new_id")
        private String newId;

        private List<Candidate> candidates;
    }

    @Data
    public static class Candidate {
        private int rank;

        @JsonProperty("matched_old_id")
        private String matchedOldId;
        private double confidence;

        @JsonProperty("is_new_disease")
        private boolean isNewDisease;
    }
}
