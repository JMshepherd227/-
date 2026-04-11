package org.example.roaddetection.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.example.roaddetection.entity.DefectEntity;

import java.util.List;

@Mapper
public interface DefectEntityMapper extends BaseMapper<DefectEntity> {
}
