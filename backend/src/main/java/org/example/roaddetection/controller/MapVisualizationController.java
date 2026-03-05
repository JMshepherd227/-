package org.example.roaddetection.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import jakarta.annotation.Resource;
import org.example.roaddetection.common.Result;
import org.example.roaddetection.entity.DefectDetail;
import org.example.roaddetection.entity.InspectionImage;
import org.example.roaddetection.mapper.DefectDetailMapper;
import org.example.roaddetection.mapper.InspectionImageMapper;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/v1/map")
public class MapVisualizationController {
    @Resource
    private InspectionImageMapper inspectionImageMapper;

    @GetMapping("/defects")
    public Result<List<InspectionImage>> getDefects(
            @RequestParam("maxLat") double maxLat,
            @RequestParam("maxLng") double maxLng,
            @RequestParam("minLat") double minLat,
            @RequestParam("minLng") double minLng
    ) {
        try {
            List<InspectionImage> list = inspectionImageMapper.selectDefectsInViewport(minLat, maxLat, minLng, maxLng);
            return Result.success(list);
        } catch (Exception e) {
            return Result.fail("查询失败: " + e.getMessage());
        }
    }
}
