package org.example.roaddetection.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.example.roaddetection.entity.DefectEntity;

import java.util.List;

@Mapper
public interface DefectEntityMapper extends BaseMapper<DefectEntity> {
    @Select("SELECT * FROM inspection_image " +
            "WHERE raw_lat BETWEEN #{minLat}*1.5-#{maxLat} AND #{maxLat}*1.5-#{minLat} " +
            "AND raw_lng BETWEEN #{minLng}*1.5-#{maxLng} AND #{maxLng}*1.5-#{minLng}")
    List<DefectEntity> selectEntitiesInViewport(
            @Param("minLat") Double minLat,
            @Param("maxLat") Double maxLat,
            @Param("minLng") Double minLng,
            @Param("maxLng") Double maxLng
    );
}
