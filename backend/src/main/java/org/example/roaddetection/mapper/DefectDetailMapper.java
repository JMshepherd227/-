package org.example.roaddetection.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.*;
import org.example.roaddetection.entity.DefectDetail;

import java.util.List;

@Mapper
public interface DefectDetailMapper extends BaseMapper<DefectDetail> {
    @Select("SELECT d.*, i.result_image_url, i.original_image_url, i.capture_time, i.create_time" +
            "FROM defect_detail d " +
            "JOIN inspection_image i ON d.image_id = i.id " +
            "WHERE d.entity_id = #{entityId} " +
            "ORDER BY i.capture_time DESC")
    List<DefectDetail> selectDetailsWithImageByEntityId(@Param("entityId") Long entityId);
}
