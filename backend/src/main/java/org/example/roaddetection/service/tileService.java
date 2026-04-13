package org.example.roaddetection.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

@Slf4j
@Service
@RequiredArgsConstructor
public class tileService {
    private final StringRedisTemplate stringRedisTemplate;

    public void evictTileCache(Double lng, Double lat) {
        if (lng == null || lat == null) return;
        int[] zoomLevels = {10, 11, 12, 13, 14, 15, 16, 17, 18};
        for (int z : zoomLevels) {
            int x = lon2tileX(lng, z);
            int y = lat2tileY(lat, z);
            String cacheKey = String.format("map:tile:%d:%d:%d", z, x, y);
            stringRedisTemplate.delete(cacheKey);
            log.info("清除瓦片缓存: {}", cacheKey);
        }
    }

    private int lon2tileX(double lon, int z) {
        return (int) Math.floor((lon + 180.0) / 360.0 * (1 << z));
    }

    private int lat2tileY(double lat, int z) {
        double r = Math.toRadians(lat);
        return (int) Math.floor((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2 * (1 << z));
    }
}
