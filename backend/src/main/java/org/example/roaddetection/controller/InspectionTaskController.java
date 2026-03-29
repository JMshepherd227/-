package org.example.roaddetection.controller;

import io.swagger.v3.oas.annotations.Operation;
import lombok.RequiredArgsConstructor;
import org.example.roaddetection.common.Result;
import org.example.roaddetection.dto.TaskUpdateDTO;
import org.example.roaddetection.dto.TaskQueryDTO;
import org.example.roaddetection.entity.InspectionTask;
import org.example.roaddetection.service.InspectionTaskService;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/v1/tasks")
@RequiredArgsConstructor
public class InspectionTaskController {
    private final InspectionTaskService  inspectionTaskService;

    /**
     * 创建任务
     * @param dto 任务详情信息，包含任务名称、指定无人机id、航线信息
     * @return 接口响应信息
     */
    @Transactional(rollbackFor = Exception.class)
    @PostMapping("")
    public Result<InspectionTask> taskCreate(@RequestBody TaskUpdateDTO dto) {
        inspectionTaskService.createTask(dto);
        return Result.success();
    }

    /**
     * 删除任务
     * @param id 任务id
     * @return 接口响应信息
     */
    @Transactional(rollbackFor = Exception.class)
    @DeleteMapping("/{id}")
    public Result<InspectionTask> taskDelete(@PathVariable Long id) {
        inspectionTaskService.deleteTask(id);
        return Result.success();
    }

    /**
     * 修改任务
     * @param dto 任务数据，包含任务名称、指定无人机id、航线信息
     * @param id 任务id
     * @return 接口响应信息
     */
    @Transactional(rollbackFor = Exception.class)
    @PutMapping("/{id}")
    public Result<InspectionTask> taskUpdate(@RequestBody TaskUpdateDTO dto, @PathVariable Long id) {
        inspectionTaskService.updateTask(dto, id);
        return Result.success();
    }

    /**
     * 获取任务详情
     * @param id 任务id
     * @return 接口响应信息
     */
    @Transactional(rollbackFor = Exception.class)
    @GetMapping("/{id}")
    public Result<InspectionTask> getTask(@PathVariable Long id) {
        return Result.success(inspectionTaskService.getTask(id));
    }

    /**
     * 获取任务列表（支持多条件筛选）
     *
     * 可根据任务名称、任务状态、创建时间范围、病害数量范围等条件进行筛选。
     * 若不传入任何参数，则默认返回全部任务列表。
     *
     * @param query 任务查询条件
     *              - taskName          任务名称(模糊查询)
     *              - status            任务状态
     *              - DroneId           无人机ID
     *              - DefectCount       病害数量(精确查询)
     *              - minDefectCount    最小病害数量
     *              - maxDefectCount    最大病害数量
     *
     * @return Result<List<InspectionTask>>
     *         code = 200 表示成功
     *         data = 任务列表
     */
    @Transactional(rollbackFor = Exception.class)
    @GetMapping()
    public Result<List<InspectionTask>> getTaskList(TaskQueryDTO query) {
        return Result.success(inspectionTaskService.searchTasks(query));
    }

    /**
     * 开始任务
     * @param id 任务id
     * @return 任务响应信息
     */
    @Transactional(rollbackFor = Exception.class)
    @PutMapping("/{id}/start")
    public Result<String> taskStart(@PathVariable Long id) {
        inspectionTaskService.startTaskByID(id);
        return Result.success("任务已下发，无人机起飞中...");
    }

    /**
     * 结束任务，本接口由无人机调用
     * @param droneId 无人机ID
     * @return 任务响应信息
     */
    @Transactional(rollbackFor = Exception.class)
    @PutMapping("/{droneId}/finish")
    public Result<String> taskFinish(@PathVariable Long droneId) {
        inspectionTaskService.finishTaskByDrone(droneId);
        return Result.success("任务已结束");
    }
}
