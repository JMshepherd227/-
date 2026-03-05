package org.example.roaddetection.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.*;
import org.example.roaddetection.entity.DefectDetail;
import java.util.List;

@Mapper
public interface DefectDetailMapper extends BaseMapper<DefectDetail> {
    @Select("SELECT d.* " +
            "FROM defect_detail d " +
            "JOIN inspection_image i ON d.image_id = i.id " +
            "WHERE i.matched_lat BETWEEN #{minLat} AND #{maxLat} " +
            "AND i.matched_lng BETWEEN #{minLng} AND #{maxLng}")
    List<DefectDetail> selectByViewport(
            @Param("minLat") Double minLat,
            @Param("maxLat") Double maxLat,
            @Param("minLng") Double minLng,
            @Param("maxLng") Double maxLng
    );
}
