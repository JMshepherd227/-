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
        entityMapper.insert(newEntity); // 此时自动生成了真实 ID

        // 2. 批量更新详情表，将这段任务期间的记录全挂在这个真实 ID 下
        detailMapper.update(null, new LambdaUpdateWrapper<DefectDetail>()
                .eq(DefectDetail::getTempEntityId, tempId)
                .set(DefectDetail::getEntityId, newEntity.getId()));

        log.info("【GNN创建新实体】真实ID: {}, 临时ID: {}", newEntity.getId(), tempId);
    }

    /**
     * 更新旧病害：将临时病害绑定到已存在的历史实体上
     */
    @Transactional(rollbackFor = Exception.class)
    public void updateOldDisease(Long oldEntityId, String tempId) {
        // 批量更新详情表，认祖归宗
        detailMapper.update(null, new LambdaUpdateWrapper<DefectDetail>()
                .eq(DefectDetail::getTempEntityId, tempId)
                .set(DefectDetail::getEntityId, oldEntityId));

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
        int chunkSize = 50;
        double buffer = 10.0 / 111000.0;

        Set<DefectEntity> resultSet = new HashSet<>();
        for (int i = 0; i < tempEntities.size(); i += chunkSize) {
            int end = Math.min(i + chunkSize, tempEntities.size());
            List<TempEntityDTO> chunk = tempEntities.subList(i, end);

            double minLng = chunk.stream().mapToDouble(TempEntityDTO::getLng).min().orElse(0) - buffer;
            double maxLng = chunk.stream().mapToDouble(TempEntityDTO::getLng).max().orElse(0) + buffer;
            double minLat = chunk.stream().mapToDouble(TempEntityDTO::getLat).min().orElse(0) - buffer;
            double maxLat = chunk.stream().mapToDouble(TempEntityDTO::getLat).max().orElse(0) + buffer;

            resultSet.addAll(entityMapper.selectList(
                    new LambdaQueryWrapper<DefectEntity>()
                            .between(DefectEntity::getLng, minLng, maxLng)
                            .between(DefectEntity::getLat, minLat, maxLat)
                            .eq(DefectEntity::getStatus, "ACTIVE")
            ));
        }
        return new ArrayList<>(resultSet);
    }
}
