package org.example.roaddetection.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Update;
import org.example.roaddetection.entity.InspectionTask;

@Mapper
public interface InspectionTaskMapper extends BaseMapper<InspectionTask> {
    @Update("UPDATE inspection_task SET defect_count = IFNULL(defect_count, 0) + #{count} WHERE id = #{id}")
    void increaseDefectCount(@Param("id") Long id, @Param("count") Integer count);
}
