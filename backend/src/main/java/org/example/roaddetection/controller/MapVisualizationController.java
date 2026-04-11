package org.example.roaddetection.controller;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.example.roaddetection.common.Result;
import org.example.roaddetection.common.TileBBox;
import org.example.roaddetection.entity.DefectEntity;
import org.example.roaddetection.mapper.DefectEntityMapper;
import org.example.roaddetection.util.TileUtil;
import org.example.roaddetection.entity.DefectDetail;
import org.example.roaddetection.entity.InspectionImage;
import org.example.roaddetection.mapper.DefectDetailMapper;
import org.example.roaddetection.mapper.InspectionImageMapper;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.web.bind.annotation.*;

import java.util.Collections;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.ThreadLocalRandom;
import java.util.concurrent.TimeUnit;

@Slf4j
@RestController
@RequestMapping("/api/v1/map")
@RequiredArgsConstructor
public class MapVisualizationController {
    private final InspectionImageMapper inspectionImageMapper;
    private final DefectDetailMapper defectDetailMapper;
    private final RedisTemplate<String, Object> redisTemplate;
    private final StringRedisTemplate stringRedisTemplate;
    private final ObjectMapper objectMapper;
    /**
     *  获取视口内的图片打点
     * @param z 缩放等级
     * @param x 瓦片x坐标
     * @param y 瓦片y坐标
     * @return 包含巡检图片的接口响应
     */
    @GetMapping("/tile")
    public Result<List<InspectionImage>> getDefectsInViewport(
            @RequestParam int z,
            @RequestParam int x,
            @RequestParam int y
    ) {
        String cacheKey = String.format("map:tile:%d:%d:%d", z, x, y);
        String lockKey = "lock:" + cacheKey;

        int maxRetries = 5;

        TileBBox bbox = TileUtil.tileToBBox(z, x, y);

        double maxLng = bbox.getMaxLng();
        double maxLat = bbox.getMaxLat();
        double minLng = bbox.getMinLng();
        double minLat = bbox.getMinLat();

        try {
            for (int retryCount = 0; retryCount < maxRetries; retryCount++) {
                String json = stringRedisTemplate.opsForValue().get(cacheKey);

                if (json != null) {
                    log.info("命中 Redis 缓存: {}", cacheKey);

                    //防穿透
                    if (json.equals("[]")) {
                        return Result.success(Collections.emptyList());
                    }

                    try {
                        List<InspectionImage> cachedData = objectMapper.readValue(json, new TypeReference<List<InspectionImage>>() {});
                        return Result.success(cachedData);
                    } catch (Exception e) {
                        log.error("反序列化失败，删除缓存: {}", cacheKey, e);
                        stringRedisTemplate.delete(cacheKey);
                    }
                }

                String lockValue = UUID.randomUUID().toString();
                Boolean locked = stringRedisTemplate.opsForValue().setIfAbsent(lockKey, lockValue, 10, TimeUnit.SECONDS);

                if (Boolean.TRUE.equals(locked)) {
                    log.warn("获取锁成功，未命中缓存，正在查询数据库...");
                    try {
                        // 查询数据库
                        List<InspectionImage> dbData =
                                inspectionImageMapper.selectImagesInViewport(minLat, maxLat, minLng, maxLng);
                        // 防穿透
                        if (dbData == null || dbData.isEmpty()) {
                            stringRedisTemplate.opsForValue().set(cacheKey, "[]", 120, TimeUnit.SECONDS);
                            return Result.success(Collections.emptyList());
                        }
                        // 转JSON
                        String jsonData = objectMapper.writeValueAsString(dbData);
                        // 随机 TTL
                        int ttl = 300 + ThreadLocalRandom.current().nextInt(60);

                        stringRedisTemplate.opsForValue().set(cacheKey, jsonData, ttl, TimeUnit.SECONDS);
                        log.info("写入 Redis 缓存: {}", cacheKey);

                        return Result.success(dbData);
                    } finally {
                        // 确保只释放自己的锁
                        String luaScript =
                                "if redis.call('get', KEYS[1]) == ARGV[1] then " +
                                "   return redis.call('del', KEYS[1]) " +
                                "else return 0 end";

                        redisTemplate.execute(
                                new DefaultRedisScript<>(luaScript, Long.class),
                                Collections.singletonList(lockKey),
                                lockValue
                        );
                    }
                } else {
                    // 没有拿到锁，说明有其他线程正在查数据库，休眠 50ms 后进入下一次 while 循环重试
                    try {
                        Thread.sleep(200);
                    } catch (InterruptedException ie) {
                        Thread.currentThread().interrupt();  // 恢复中断标志
                        return Result.fail("查询被中断");
                    }
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
     * 获取病害实体的所有历史观测记录（自带图片URL，按时间倒序）
     * 图片url为相对路径，需要项目根路径+图片url进行拼接
     * @param entityId 病害实体id
     * @return 包含病害详情列表的接口响应
     */
    @GetMapping("/{entityId}/details")
    public Result<List<DefectDetail>> getDetail(@PathVariable("entityId") Long entityId) {
        try {
            List<DefectDetail> details = defectDetailMapper.selectDetailsWithImageByEntityId(entityId);
            return Result.success(details);
        } catch (Exception e) {
            return Result.fail("查询失败: " + e.getMessage());
        }
    }
}
