package org.example.roaddetection.controller;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.example.roaddetection.common.Result;
import org.example.roaddetection.common.TileBBox;
import org.example.roaddetection.util.TileUtil;
import org.example.roaddetection.entity.DefectDetail;
import org.example.roaddetection.entity.InspectionImage;
import org.example.roaddetection.mapper.DefectDetailMapper;
import org.example.roaddetection.mapper.InspectionImageMapper;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.web.bind.annotation.*;

import java.util.Collections;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.ThreadLocalRandom;
import java.util.concurrent.TimeUnit;

@Slf4j
@RestController
@RequestMapping("/api/v1/map")
public class MapVisualizationController {
    @Resource
    private InspectionImageMapper inspectionImageMapper;
    @Resource
    private DefectDetailMapper defectDetailMapper;
    @Resource
    private RedisTemplate<String, Object> redisTemplate;

    /**
     *  获取视口内的病害点
     * @param z 缩放等级
     * @param x 瓦片x坐标
     * @param y 瓦片y坐标
     * @return 包含病害点的接口响应
     */
    @GetMapping("/tile")
    public Result<List<InspectionImage>> getDefectsInViewport(
            @RequestParam int z,
            @RequestParam int x,
            @RequestParam int y
    ) {
        String cacheKey = String.format("map:tile:%d:%d:%d", z, x, y);
        String lockKey = "lock:" + cacheKey;

        int maxRetries = 20;

        TileBBox bbox = TileUtil.tileToBBox(z, x, y);

        double maxLng = bbox.getMaxLng();
        double maxLat = bbox.getMaxLat();
        double minLng = bbox.getMinLng();
        double minLat = bbox.getMinLat();

        try {
            for (int retryCount = 0; retryCount < maxRetries; retryCount++) {
                @SuppressWarnings("unchecked")
                List<InspectionImage> cachedData = (List<InspectionImage>) redisTemplate.opsForValue().get(cacheKey);
                if (cachedData != null) {
                    log.info("命中 Redis 缓存: {}", cacheKey);
                    return Result.success(cachedData);
                }

                String lockValue = UUID.randomUUID().toString();
                Boolean locked = redisTemplate.opsForValue().setIfAbsent(lockKey, lockValue, 10, TimeUnit.SECONDS);

                if (Boolean.TRUE.equals(locked)) {
                    log.warn("获取锁成功，未命中缓存，正在查询数据库...");
                    try {
                        @SuppressWarnings("unchecked")
                        List<InspectionImage> doubleCheckCache = (List<InspectionImage>) redisTemplate.opsForValue().get(cacheKey);
                        if (doubleCheckCache != null) {
                            return Result.success(doubleCheckCache);
                        }
                        //读取数据库
                        List<InspectionImage> dbData = inspectionImageMapper.selectDefectsInViewport(minLat, maxLat, minLng, maxLng);
                        //存入空列表，防止缓存穿透
                        if (dbData == null || dbData.isEmpty()) {
                            redisTemplate.opsForValue().set(cacheKey, Collections.emptyList(), 8, TimeUnit.MINUTES);
                            return Result.success(Collections.emptyList());
                        }
                        //随机TTL
                        int ttl = 300 + ThreadLocalRandom.current().nextInt(60);
                        redisTemplate.opsForValue().set(cacheKey, dbData, ttl, TimeUnit.SECONDS);
                        log.info("写入 Redis 缓存: {}", cacheKey);

                        return Result.success(dbData);
                    } finally {
                        // 确保只释放自己的锁
                        Object currentLockVal = redisTemplate.opsForValue().get(lockKey);
                        if (lockValue.equals(currentLockVal)) {
                            redisTemplate.delete(lockKey);
                        }
                    }
                } else {
                    // 没有拿到锁，说明有其他线程正在查数据库，休眠 50ms 后进入下一次 while 循环重试
                    Thread.sleep(50);
                }
            }

            log.error("系统繁忙，等待获取缓存锁超时: {}", cacheKey);
            return Result.fail("当前查看该区域的人数过多，系统繁忙，请稍后再试");

        } catch (Exception e) {
            log.error("地图数据查询异常", e);
            return Result.fail("查询失败: " + e.getMessage());
        }
    }


    /**
     * 获取某张照片的病害详情
     * @param imageId 无人机照片id
     * @return 包含该照片的病害详情列表的接口响应
     */
    @GetMapping("/{imageId}/details")
    public Result<List<DefectDetail>> getDetail(@PathVariable("imageId") Long imageId) {
        try {
            QueryWrapper<DefectDetail> wrapper = new QueryWrapper<>();
            wrapper.eq("image_id", imageId);

            List<DefectDetail> idList = defectDetailMapper.selectList(wrapper);
            return Result.success(idList);
        } catch (Exception e) {
            return Result.fail("查询失败: " + e.getMessage());
        }
    }
}
