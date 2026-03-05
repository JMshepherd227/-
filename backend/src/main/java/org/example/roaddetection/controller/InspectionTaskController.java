package org.example.roaddetection.controller;

import jakarta.annotation.Resource;
import org.example.roaddetection.common.Result;
import org.example.roaddetection.entity.InspectionTask;
import org.example.roaddetection.mapper.InspectionTaskMapper;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/v1/tasks")
public class InspectionTaskController {
    @Resource
    private InspectionTaskMapper inspectionTaskMapper;

    /**
     * 创建新任务
     */
    @PostMapping("")
    public Result<InspectionTask> taskCreate(@RequestBody InspectionTask inspectionTask) {
        try {
            inspectionTaskMapper.insert(inspectionTask);
            return Result.success();
        } catch (Exception e) {
            return Result.fail("创建失败" + e.getMessage());
        }
    }

    /**
     * 删除任务
     */
    @DeleteMapping("/{id}")
    public Result<InspectionTask> taskDelete(@PathVariable Long id) {
        try {
            if(inspectionTaskMapper.selectById(id)==null)
                return Result.fail("任务不存在");
            inspectionTaskMapper.deleteById(id);
            return Result.success();
        } catch (Exception e) {
            return Result.fail("删除失败" + e.getMessage());
        }
    }

    /**
     * 修改任务
     */
    @PutMapping("/{id}")
    public Result<InspectionTask> taskUpdate(@RequestBody InspectionTask inspectionTask, @PathVariable Long id) {
        try {
            inspectionTask.setId(id);
            if(inspectionTaskMapper.selectById(id)==null)
                return Result.fail("任务不存在");
            inspectionTaskMapper.updateById(inspectionTask);
            return Result.success();
        } catch (Exception e) {
            return Result.fail("修改失败" + e.getMessage());
        }
    }

    /**
     * 查询任务
     */
    @GetMapping("/{id}")
    public Result<InspectionTask> getTask(@PathVariable Long id) {
        try {
            InspectionTask inspectionTask = inspectionTaskMapper.selectById(id);
            if(inspectionTask==null)
                return Result.fail("任务不存在");
            return Result.success(inspectionTask);
        } catch (Exception e) {
            return Result.fail("获取失败" + e.getMessage());
        }
    }

    /**
     * 获取任务列表
     */
    @GetMapping()
    public Result<List<InspectionTask>> getTaskList() {
        try {
            List<InspectionTask> inspectionTaskList = inspectionTaskMapper.selectList(null);
            return Result.success(inspectionTaskList);
        } catch (Exception e) {
            return Result.fail("获取失败" + e.getMessage());
        }
    }

    /**
     * 开始任务
     */
    @PutMapping("/{id}/start")
    public Result<List<InspectionTask>> taskStart(@PathVariable Long id) {
        try {
            InspectionTask inspectionTask = inspectionTaskMapper.selectById(id);
            if(inspectionTask==null)
                return Result.fail("任务不存在");
            inspectionTask.setStatus(1);
            inspectionTaskMapper.updateById(inspectionTask);
            return Result.success();
        } catch (Exception e) {
            return Result.fail("error：" + e.getMessage());
        }
    }

    /**
     * 结束任务
     */
    @PutMapping("/{id}/finish")
    public Result<List<InspectionTask>> taskFinish(@PathVariable Long id) {
        try {
            InspectionTask inspectionTask = inspectionTaskMapper.selectById(id);
            if(inspectionTask==null)
                return Result.fail("任务不存在");
            inspectionTask.setStatus(2);
            inspectionTaskMapper.updateById(inspectionTask);
            return Result.success();
        } catch (Exception e) {
            return Result.fail("error：" + e.getMessage());
        }
    }
}
