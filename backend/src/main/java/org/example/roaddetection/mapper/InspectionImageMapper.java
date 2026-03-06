package org.example.roaddetection.mapper;

import org.apache.ibatis.annotations.Mapper;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.example.roaddetection.entity.InspectionImage;

import java.util.List;

@Mapper
public interface InspectionImageMapper extends BaseMapper<InspectionImage> {
    @Select("SELECT * FROM inspection_image " +
            "WHERE is_defect = 1 " +
            "AND matched_lat BETWEEN #{minLat}*2-#{maxLat} AND #{maxLat}*2-#{minLat} " +
            "AND matched_lng BETWEEN #{minLng}*2-#{maxLng} AND #{maxLng}*2-#{minLng}")
    List<InspectionImage> selectDefectsInViewport(
            @Param("minLat") Double minLat,
            @Param("maxLat") Double maxLat,
            @Param("minLng") Double minLng,
            @Param("maxLng") Double maxLng
    );
}
