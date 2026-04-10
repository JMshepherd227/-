package org.example.roaddetection.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.example.roaddetection.dto.GnnMatchRequest;
import org.example.roaddetection.dto.GnnMatchResponse;
import org.example.roaddetection.dto.TempEntityDTO;
import org.example.roaddetection.entity.DefectEntity;
import org.example.roaddetection.events.TaskFinishEvent;
import org.springframework.context.event.EventListener;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import cn.hutool.json.JSONUtil;

import java.util.*;

@Slf4j
@Service
@RequiredArgsConstructor
public class GlobalMatchService {

    private final StringRedisTemplate stringRedisTemplate;
    private final AiService aiService;
    private final TempEntityService tempEntityService;

    @Async("globalMatchExecutor")
    @EventListener
    public void onTaskFinished(TaskFinishEvent event) {
        Long taskId = event.taskId();
        log.info("【启动全局对齐引擎】开始处理任务 ID: {}", taskId);
        String redisKey = "TaskTempEntities:" + taskId;

        try {
            Map<Object, Object> redisEntries = stringRedisTemplate.opsForHash().entries(redisKey);
            if (redisEntries.isEmpty()) {
                log.info("【全局对齐结束】该任务无任何病害记录。TaskID: {}", taskId);
                return;
            }

            // 1. 【核心优化】: 将 List 转为 Map，方便后续 O(1) 极速查找！
            Map<String, TempEntityDTO> newPointMap = new HashMap<>();
            List<GnnMatchRequest.PointDto> newPts = new ArrayList<>();

            for (Object jsonStr : redisEntries.values()) {
                TempEntityDTO dto = JSONUtil.toBean(jsonStr.toString(), TempEntityDTO.class);
                newPointMap.put(dto.getTempId(), dto);
                newPts.add(new GnnMatchRequest.PointDto(dto.getTempId(), dto.getLng(), dto.getLat(), dto.getDefectType()));
            }

            // 2. 提取历史病害，同样转为 Map
            List<DefectEntity> oldEntities = tempEntityService.fetchNearbyHistoricalDefects(new ArrayList<>(newPointMap.values()));
            Map<String, DefectEntity> oldEntityMap = new HashMap<>();
            List<GnnMatchRequest.PointDto> oldPts = new ArrayList<>();

            for (DefectEntity oldEntity : oldEntities) {
                String oldIdStr = String.valueOf(oldEntity.getId());
                oldEntityMap.put(oldIdStr, oldEntity);
                oldPts.add(new GnnMatchRequest.PointDto(oldIdStr, oldEntity.getLng(), oldEntity.getLat(), oldEntity.getDefectType()));
            }

            // 3. 调用 GNN
            GnnMatchResponse response = aiService.GnnMatcher(oldPts, newPts);
            if (response == null || response.getResults() == null) return;

            // 4. 遍历结果决策
            for (GnnMatchResponse.MatchResultItem item : response.getResults()) {
                String newId = item.getNewId();
                TempEntityDTO currentTempDto = newPointMap.get(newId);
                boolean matched = false;

                for (GnnMatchResponse.Candidate candidate : item.getCandidates()) {
                    if (candidate.isNewDisease()) {
                        if (candidate.getConfidence() > 0.5) {
                            tempEntityService.saveAsNewDisease(newId, currentTempDto);
                            matched = true;
                            break;
                        }
                        continue;
                    }

                    String oldIdStr = candidate.getMatchedOldId();
                    Long oldEntityId = Long.parseLong(oldIdStr);

                    if (candidate.getConfidence() > 0.85) {
                        tempEntityService.updateOldDisease(oldEntityId, newId);
                        matched = true;
                        break;
                    } else if (candidate.getConfidence() > 0.20) {
                        // 调用 SIFT 兜底验证
                        boolean isVisualMatch = tempEntityService.checkWithSift(oldEntityId, newId);
                        if (isVisualMatch) {
                            tempEntityService.updateOldDisease(oldEntityId, newId);
                            matched = true;
                            break;
                        } else {
                            log.info("SIFT 拒绝了匹配 {} -> {}", newId, oldIdStr);
                        }
                    }
                }

                if (!matched) {
                    tempEntityService.saveAsNewDisease(newId, currentTempDto);
                }
            }
        } catch (Exception e) {
            log.error("【GNN对齐失败】TaskID: {}, 原因: {}", taskId, e.getMessage(), e);
        } finally {
            stringRedisTemplate.delete(redisKey); // 清理内存
        }
    }
}
