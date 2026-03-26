package org.example.roaddetection.controller;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.RequiredArgsConstructor;
import org.example.roaddetection.common.Result;
import org.example.roaddetection.events.TelemetryEvent;
import org.example.roaddetection.service.DroneService;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import java.util.Map;

import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping("/api/v1/drones")
@RequiredArgsConstructor
public class DroneIngestController {
    private final DroneService droneService;
    private final ApplicationEventPublisher eventPublisher;

    /**
     * 无人机位置上报
     */
    @PostMapping("/telemetry")
    public Result<String> receiveTelemetry(@RequestBody Map<String, Object> telemetryData) {
        eventPublisher.publishEvent(new TelemetryEvent(telemetryData));
        return Result.success("遥测数据已广播");
    }

    @Operation(summary = "无人机抓拍图片与位置上报")
    @PostMapping(value = "/upload", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public Result<String> uploadImage(
            @RequestParam("taskId") Long taskId,
            @RequestParam("droneId") Long droneId,
            @RequestParam("lng") Double lng,
            @RequestParam("lat") Double lat,
            @Parameter(description = "图片文件", content = @Content(mediaType = MediaType.MULTIPART_FORM_DATA_VALUE,
                    schema = @Schema(type = "string", format = "binary")))
            @RequestPart("file") MultipartFile file) throws Exception {
        droneService.processUploadSync(taskId,droneId,lng,lat,file);
        return Result.success("图片上传成功");
    }
}


