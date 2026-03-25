package org.example.roaddetection.enums;

import com.baomidou.mybatisplus.annotation.EnumValue;
import lombok.Getter;

@Getter
public enum TaskStatus {
    WAITING(0, "未开始"),
    RUNNING(1, "执行中"),
    FINISHED(2, "已完成");

    @EnumValue
    private final int value;
    private final String desc;

    TaskStatus(int value, String desc) {
        this.value = value;
        this.desc = desc;
    }

}
