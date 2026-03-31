package org.example.roaddetection.controller;

import lombok.RequiredArgsConstructor;
import org.example.roaddetection.common.Result;
import org.example.roaddetection.events.TelemetryEvent;
import org.example.roaddetection.service.DroneService;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.http.MediaType;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;
import java.util.Map;

import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping("/api/v1/drones")
@RequiredArgsConstructor
public class DroneIngestController {
    private final DroneService droneService;
    private final ApplicationEventPublisher eventPublisher;

    @PostMapping("/telemetry")
    public Result<String> receiveTelemetry(@RequestBody Map<String, Object> telemetryData) {
        eventPublisher.publishEvent(new TelemetryEvent(telemetryData));
        return Result.success("遥测数据已广播");
    }

    @PostMapping(value = "/upload", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    @Transactional(rollbackFor = Exception.class)
    public Result<String> uploadImage(
            @RequestParam("taskId") Long taskId,
            @RequestParam("droneId") Long droneId,
            @RequestParam("lng") Double lng,
            @RequestParam("lat") Double lat,
            @RequestParam("altitude") Double altitude,
            @RequestParam("yaw") Double yaw,
            @RequestParam("pitch") Double pitch,
            @RequestParam("roll") Double roll,
            @RequestParam("fov") Double fov,
            @RequestPart("file") MultipartFile file) throws Exception {
        droneService.processUploadSync(taskId, droneId, lng, lat, altitude, yaw, pitch, roll, fov, file);
        return Result.success("图片上传成功");
    }
}


