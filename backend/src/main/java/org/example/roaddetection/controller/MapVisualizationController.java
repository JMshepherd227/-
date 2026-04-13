package org.example.roaddetection.controller;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.example.roaddetection.common.Result;
import org.example.roaddetection.common.TileBBox;
import org.example.roaddetection.entity.DefectDetail;
import org.example.roaddetection.entity.DefectEntity;
import org.example.roaddetection.mapper.DefectDetailMapper;
import org.example.roaddetection.mapper.DefectEntityMapper;
import org.example.roaddetection.util.TileUtil;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.transaction.annotation.Transactional;
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

    private final DefectEntityMapper defectEntityMapper;
    private final DefectDetailMapper defectDetailMapper;
    private final StringRedisTemplate stringRedisTemplate;
    private final ObjectMapper objectMapper;

    /**
     * 获取视口内的病害实体打点
     *
     * @param z 缩放等级
     * @param x 瓦片x坐标
     * @param y 瓦片y坐标
     * @return 包含病害实体列表的接口响应
     */
    @GetMapping("/tile")
    public Result<List<DefectEntity>> getDefectsInViewport(
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

        String luaScript =
                "if redis.call('get', KEYS[1]) == ARGV[1] then " +
                "   return redis.call('del', KEYS[1]) " +
                "else return 0 end";

        try {
            for (int retryCount = 0; retryCount < maxRetries; retryCount++) {

                // ① 先尝试读缓存
                String json = stringRedisTemplate.opsForValue().get(cacheKey);
                if (json != null) {
                    log.info("命中 Redis 缓存: {}", cacheKey);
                    if ("[]".equals(json)) {
                        return Result.success(Collections.emptyList());
                    }
                    try {
                        List<DefectEntity> cachedData = objectMapper.readValue(
                                json, new TypeReference<List<DefectEntity>>() {});
                        return Result.success(cachedData);
                    } catch (Exception e) {
                        log.error("反序列化失败，删除缓存: {}", cacheKey, e);
                        stringRedisTemplate.delete(cacheKey);
                    }
                }

                // ② 缓存未命中，尝试抢锁
                String lockValue = UUID.randomUUID().toString();
                Boolean locked = stringRedisTemplate.opsForValue()
                        .setIfAbsent(lockKey, lockValue, 10, TimeUnit.SECONDS);

                if (Boolean.TRUE.equals(locked)) {
                    log.info("获取锁成功，准备查询数据库: {}", cacheKey);
                    try {
                        // ③ Double-Check：抢到锁后再查一次缓存
                        String jsonAfterLock = stringRedisTemplate.opsForValue().get(cacheKey);
                        if (jsonAfterLock != null) {
                            log.info("Double-Check 命中缓存，无需查库: {}", cacheKey);
                            if ("[]".equals(jsonAfterLock)) {
                                return Result.success(Collections.emptyList());
                            }
                            List<DefectEntity> cachedData = objectMapper.readValue(
                                    jsonAfterLock, new TypeReference<List<DefectEntity>>() {});
                            return Result.success(cachedData);
                        }

                        // ④ 查数据库
                        List<DefectEntity> dbData =
                                defectEntityMapper.selectEntitiesInViewport(minLat, maxLat, minLng, maxLng);

                        if (dbData == null || dbData.isEmpty()) {
                            stringRedisTemplate.opsForValue().set(cacheKey, "[]", 120, TimeUnit.SECONDS);
                            return Result.success(Collections.emptyList());
                        }

                        // ⑤ 写缓存，随机 TTL 防雪崩
                        String jsonData = objectMapper.writeValueAsString(dbData);
                        int ttl = 300 + ThreadLocalRandom.current().nextInt(60);
                        stringRedisTemplate.opsForValue().set(cacheKey, jsonData, ttl, TimeUnit.SECONDS);
                        log.info("写入 Redis 缓存: {}", cacheKey);

                        return Result.success(dbData);

                    } finally {
                        // ⑥ 释放锁
                        stringRedisTemplate.execute(
                                new DefaultRedisScript<>(luaScript, Long.class),
                                Collections.singletonList(lockKey),
                                lockValue
                        );
                    }

                } else {
                    log.debug("未获取到锁，等待重试 ({}/{}): {}", retryCount + 1, maxRetries, cacheKey);
                    try {
                        Thread.sleep(200);
                    } catch (InterruptedException ie) {
                        Thread.currentThread().interrupt();
                        return Result.fail("查询被中断");
                    }
                }
            }

            log.error("超出最大重试次数，获取缓存锁超时: {}", cacheKey);
            return Result.fail("当前查看该区域的人数过多，系统繁忙，请稍后再试");

        } catch (Exception e) {
            log.error("地图数据查询异常", e);
            return Result.fail("查询失败: " + e.getMessage());
        }
    }

    /**
     * 获取病害实体的所有历史观测记录（自带图片URL，按时间倒序）
     *
     * @param entityId 病害实体id
     * @return 包含病害详情列表的接口响应
     */
    @Transactional(rollbackFor = Exception.class)
    @GetMapping("/{entityId}/details")
    public Result<List<DefectDetail>> getDetail(@PathVariable("entityId") Long entityId) {
        List<DefectDetail> details = defectDetailMapper.selectDetailsWithImageByEntityId(entityId);
        return Result.success(details);
    }
}