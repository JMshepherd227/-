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
            "WHERE (matched_lat BETWEEN #{minLat} AND #{maxLat} OR (matched_lat IS NULL AND raw_lat BETWEEN #{minLat} AND #{maxLat})) " +
            "AND (matched_lng BETWEEN #{minLng} AND #{maxLng} OR (matched_lng IS NULL AND raw_lng BETWEEN #{minLng} AND #{maxLng}))")
    List<InspectionImage> selectImagesInViewport(
            @Param("minLat") Double minLat,
            @Param("maxLat") Double maxLat,
            @Param("minLng") Double minLng,
            @Param("maxLng") Double maxLng
    );
}
