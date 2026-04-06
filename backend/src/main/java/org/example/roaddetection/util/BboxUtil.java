package org.example.roaddetection.util;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.util.List;

public class BboxUtil {
    private static final ObjectMapper objectMapper = new ObjectMapper();

    public static List<Double> parseBbox(String bboxStr) {
        try {
            return objectMapper.readValue(bboxStr, new TypeReference<List<Double>>() {});
        } catch (Exception e) {
            throw new RuntimeException("解析 BBox 字符串失败: " + bboxStr, e);
        }
    }
}
