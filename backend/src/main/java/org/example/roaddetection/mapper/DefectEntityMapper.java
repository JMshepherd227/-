package org.example.roaddetection.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.example.roaddetection.entity.DefectEntity;

import java.util.List;

@Mapper
public interface DefectEntityMapper extends BaseMapper<DefectEntity> {
    @Select("SELECT * FROM defect_entity " +
            "WHERE lat BETWEEN #{minLat} AND #{maxLat} " +
            "AND lng BETWEEN #{minLng} AND #{maxLng}")
    List<DefectEntity> selectEntitiesInViewport(
            @Param("minLat") Double minLat,
            @Param("maxLat") Double maxLat,
            @Param("minLng") Double minLng,
            @Param("maxLng") Double maxLng
    );
}
