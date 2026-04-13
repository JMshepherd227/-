package org.example.roaddetection.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.example.roaddetection.dto.AiMatchResponseDTO;
import org.example.roaddetection.dto.TempEntityDTO;
import org.example.roaddetection.entity.DefectDetail;
import org.example.roaddetection.entity.DefectEntity;
import org.example.roaddetection.entity.InspectionImage;
import org.example.roaddetection.mapper.DefectDetailMapper;
import org.example.roaddetection.mapper.DefectEntityMapper;
import org.example.roaddetection.mapper.InspectionImageMapper;
import org.example.roaddetection.util.BboxUtil;
import org.example.roaddetection.util.DistanceUtil;
import org.example.roaddetection.util.HomographyUtil;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.io.File;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

@Service
@Transactional
@Slf4j
@RequiredArgsConstructor
public class TempEntityService {
    private final DefectEntityMapper entityMapper;
    private final DefectDetailMapper detailMapper;
    private final InspectionImageMapper imageMapper;

    private final AiService aiService;
    private final tileService tileService;

    @Value("${drone.root-dir}")
    private String rootDir;

    /**
     * 新建病害：将临时 DTO 转为真实实体，并绑定详情表
     */
    @Transactional(rollbackFor = Exception.class)
    public void saveAsNewDisease(String tempId, TempEntityDTO tempDto) {
        // 1. 创建真实实体
        DefectEntity newEntity = new DefectEntity();
        newEntity.setDefectType(tempDto.getDefectType());
        newEntity.setLng(tempDto.getLng());
        newEntity.setLat(tempDto.getLat());
        newEntity.setStatus("ACTIVE");
        newEntity.setCreateTime(LocalDateTime.now());
        entityMapper.insert(newEntity);

        // 2. 批量更新详情表
        detailMapper.update(null, new LambdaUpdateWrapper<DefectDetail>()
                .eq(DefectDetail::getTempEntityId, tempId)
                .set(DefectDetail::getEntityId, newEntity.getId()));

        // 3. 清除该坐标所在瓦片的缓存
        tileService.evictTileCache(tempDto.getLng(), tempDto.getLat());

        log.info("【GNN创建新实体】真实ID: {}, 临时ID: {}", newEntity.getId(), tempId);
    }

    /**
     * 更新旧病害：将临时病害绑定到已存在的历史实体上
     */
    @Transactional(rollbackFor = Exception.class)
    public void updateOldDisease(Long oldEntityId, String tempId) {
        // 1. 查出旧实体坐标，用于清缓存
        DefectEntity oldEntity = entityMapper.selectById(oldEntityId);

        // 2. 批量更新详情表
        detailMapper.update(null, new LambdaUpdateWrapper<DefectDetail>()
                .eq(DefectDetail::getTempEntityId, tempId)
                .set(DefectDetail::getEntityId, oldEntityId));

        // 3. 清除该坐标所在瓦片的缓存
        if (oldEntity != null) {
            tileService.evictTileCache(oldEntity.getLng(), oldEntity.getLat());
        }

        log.info("【GNN匹配老实体】真实ID: {} <- 临时ID: {}", oldEntityId, tempId);
    }

    /**
     * SIFT 兜底验证逻辑：提取各自的图片和 BBox 进行几何矩阵投影
     */
    public boolean checkWithSift(Long oldEntityId, String tempNewId) {
        try {
            // 1. 拿当前病害的最新一条 Detail 记录
            DefectDetail newDetail = detailMapper.selectOne(
                    new LambdaQueryWrapper<DefectDetail>()
                            .eq(DefectDetail::getTempEntityId, tempNewId)
                            .orderByDesc(DefectDetail::getId)
                            .last("LIMIT 1"));

            // 2. 拿老病害的最新一条 Detail 记录
            DefectDetail oldDetail = detailMapper.selectOne(
                    new LambdaQueryWrapper<DefectDetail>()
                            .eq(DefectDetail::getEntityId, oldEntityId)
                            .orderByDesc(DefectDetail::getId)
                            .last("LIMIT 1"));

            if (newDetail == null || oldDetail == null) return false;

            // 3. 提取图片文件
            InspectionImage newImg = imageMapper.selectById(newDetail.getImageId());
            InspectionImage oldImg = imageMapper.selectById(oldDetail.getImageId());
            File newFile = new File(rootDir + "/" + newImg.getOriginalImageUrl());
            File oldFile = new File(rootDir + "/" + oldImg.getOriginalImageUrl());

            if (!newFile.exists() || !oldFile.exists()) return false;

            // 4. 调用 Python 算矩阵
            AiMatchResponseDTO matchResult = aiService.match(newFile, oldFile);
            if (matchResult == null || matchResult.getHomographyMatrix() == null) {
                return false;
            }

            double[][] H = matchResult.getHomographyMatrix();
            List<Double> oldBbox = BboxUtil.parseBbox(oldDetail.getBbox());
            List<Double> newBbox = BboxUtil.parseBbox(newDetail.getBbox());

            List<Double> projectedOldBbox = HomographyUtil.projectBbox(oldBbox, H);
            double iou = HomographyUtil.calculateIou(projectedOldBbox, newBbox);

            return iou > 0.3;

        } catch (Exception e) {
            log.error("SIFT 兜底验证出错", e);
            return false;
        }
    }

    /**
     * 紧贴航线提取历史病害
     */
    public List<DefectEntity> fetchNearbyHistoricalDefects(List<TempEntityDTO> tempEntities) {
        if (tempEntities == null || tempEntities.isEmpty()) {
            return new ArrayList<>();
        }

        double searchRadiusMeters = 15.0;
        double buffer = searchRadiusMeters / 111000.0;

        int chunkSize = 20;

        Set<DefectEntity> rawResultSet = new HashSet<>();

        for (int i = 0; i < tempEntities.size(); i += chunkSize) {
            int end = Math.min(i + chunkSize, tempEntities.size());
            List<TempEntityDTO> chunk = tempEntities.subList(i, end);

            LambdaQueryWrapper<DefectEntity> wrapper = new LambdaQueryWrapper<>();
            wrapper.eq(DefectEntity::getStatus, "ACTIVE");

            wrapper.and(w -> {
                for (TempEntityDTO dto : chunk) {
                    w.or(ww -> ww
                            .between(DefectEntity::getLng, dto.getLng() - buffer, dto.getLng() + buffer)
                            .between(DefectEntity::getLat, dto.getLat() - buffer, dto.getLat() + buffer)
                    );
                }
            });

            rawResultSet.addAll(entityMapper.selectList(wrapper));
        }

        List<DefectEntity> preciseResult = new ArrayList<>();

        for (DefectEntity oldDefect : rawResultSet) {
            boolean isNearby = false;
            for (TempEntityDTO newDefect : tempEntities) {
                double distance = DistanceUtil.distance(
                        oldDefect.getLat(), oldDefect.getLng(),
                        newDefect.getLat(), newDefect.getLng()
                );

                if (distance <= searchRadiusMeters) {
                    isNearby = true;
                    break;
                }
            }
            if (isNearby) {
                preciseResult.add(oldDefect);
            }
        }

        log.info("【提取历史病害】数据库粗筛: {} 条, 内存精筛后: {} 条", rawResultSet.size(), preciseResult.size());
        return preciseResult;
    }
}
