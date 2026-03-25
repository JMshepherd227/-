package org.example.roaddetection.enums;

import com.baomidou.mybatisplus.annotation.EnumValue;
import com.fasterxml.jackson.annotation.JsonValue;
import lombok.Getter;

@Getter
public enum DroneStatus {
    WAITING(0, "空闲"),
    RUNNING(1, "任务中"),
    MAINTAINING(2, "维护中");

    @EnumValue
    @JsonValue
    private final int value;
    private final String desc;

    DroneStatus(int value, String desc) {
        this.value = value;
        this.desc = desc;
    }

}
