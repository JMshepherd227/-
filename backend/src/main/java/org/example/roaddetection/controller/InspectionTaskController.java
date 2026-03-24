package org.example.roaddetection.controller;

import cn.hutool.json.JSONUtil;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import lombok.RequiredArgsConstructor;
import org.example.roaddetection.common.Result;
import org.example.roaddetection.handler.DroneWebSocketHandler;
import org.example.roaddetection.dto.TaskQueryDTO;
import org.example.roaddetection.entity.DroneDevice;
import org.example.roaddetection.entity.InspectionTask;
import org.example.roaddetection.mapper.DroneDeviceMapper;
import org.example.roaddetection.mapper.InspectionTaskMapper;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/tasks")
@RequiredArgsConstructor
public class InspectionTaskController {
    private final InspectionTaskMapper inspectionTaskMapper;
    private final DroneDeviceMapper droneDeviceMapper;
    private final DroneWebSocketHandler  webSocketHandler;

    /**
     * 创建任务
     * @param inspectionTask 任务详情信息
     * @return 接口响应信息
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
     * @param id 任务id
     * @return 接口响应信息
     */
    @DeleteMapping("/{id}")
    public Result<InspectionTask> taskDelete(@PathVariable Long id) {
        try {
            if(inspectionTaskMapper.selectById(id)==null)
                return Result.fail("任务不存在");
            if (inspectionTaskMapper.selectById(id).getStatus() == 1) {
                return Result.fail("任务正在执行，无法删除");
            }
            inspectionTaskMapper.deleteById(id);
            return Result.success();
        } catch (Exception e) {
            return Result.fail("删除失败" + e.getMessage());
        }
    }

    /**
     *
     * @param inspectionTask 任务数据
     * @param id 任务id
     * @return 接口响应信息
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
     * 获取任务详情
     * @param id 任务id
     * @return 接口响应信息
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
    @GetMapping()
    public Result<List<InspectionTask>> getTaskList(TaskQueryDTO query) {
        try {
            LambdaQueryWrapper<InspectionTask> wrapper = new LambdaQueryWrapper<>();

            wrapper.like(query.getTaskName()!=null,
                    InspectionTask::getTaskName,
                    query.getTaskName());
            wrapper.eq(query.getDroneId()!=null,
                    InspectionTask::getDroneId,
                    query.getDroneId());
            wrapper.eq(query.getStatus()!=null,
                    InspectionTask::getStatus,
                    query.getStatus());
            wrapper.eq(query.getDefectCount()!=null,
                    InspectionTask::getDefectCount,
                    query.getDefectCount());
            wrapper.ge(query.getDefectCountMin()!=null,
                    InspectionTask::getDefectCount,
                    query.getDefectCountMin());
            wrapper.le(query.getDefectCountMax()!=null,
                    InspectionTask::getDefectCount,
                    query.getDefectCountMax());

            List<InspectionTask> inspectionTaskList = inspectionTaskMapper.selectList(wrapper);
            return Result.success(inspectionTaskList);
        } catch (Exception e) {
            return Result.fail("获取失败" + e.getMessage());
        }
    }

    /**
     * 开始任务
     * @param id 任务id
     * @return 任务响应信息
     */
    @Transactional(rollbackFor = Exception.class)
    @PutMapping("/{id}/start")
    public Result<String> taskStart(@PathVariable Long id) {
        try {
            InspectionTask task = inspectionTaskMapper.selectById(id);
            if (task == null) return Result.fail("任务不存在");
            if (task.getStatus() != 0) return Result.fail("任务非未开始状态");

            DroneDevice drone = droneDeviceMapper.selectById(task.getDroneId());
            if (drone == null) return Result.fail("无人机不存在");

            if (drone.getStatus() != 0) {
                return Result.fail("无人机 " + drone.getDroneName() + " 正在执行其他任务，请先结束该任务");
            }

            task.setStatus(1);
            drone.setStatus(1);

            inspectionTaskMapper.updateById(task);
            droneDeviceMapper.updateById(drone);

            return Result.success("任务已下发，无人机起飞中...");
        } catch (Exception e) {
            return Result.fail("启动失败: " + e.getMessage());
        }
    }

    /**
     * 结束任务
     * @param droneId 无人机ID
     * @return 任务响应信息
     */
    @Transactional
    @PutMapping("/{droneId}/finish")
    public Result<String> taskFinish(@PathVariable Long droneId) {
        try {
            LambdaQueryWrapper<InspectionTask> wrapper = new LambdaQueryWrapper<>();
            wrapper.eq(InspectionTask::getDroneId, droneId)
                    .eq(InspectionTask::getStatus, 1);

            List<InspectionTask> runningTasks = inspectionTaskMapper.selectList(wrapper);

            if (runningTasks.isEmpty()) {
                return Result.fail("该无人机当前没有正在执行的任务");
            }
            InspectionTask taskToFinish = runningTasks.get(0);

            DroneDevice drone = droneDeviceMapper.selectById(droneId);
            if (drone == null) {
                return Result.fail("无人机不存在");
            }

            taskToFinish.setStatus(2);
            drone.setStatus(0);

            inspectionTaskMapper.updateById(taskToFinish);
            droneDeviceMapper.updateById(drone);

            if (webSocketHandler != null) {
                Map<String, Object> wsMessage = Map.of(
                        "type", "task_status_update",
                        "data", Map.of(
                                "taskId", taskToFinish.getId(),
                                "status", taskToFinish.getStatus(), // 2-已完成
                                "droneId", droneId,
                                "droneStatus", drone.getStatus()   // 0-空闲
                        )
                );
                webSocketHandler.broadcastMessage(JSONUtil.toJsonStr(wsMessage));
            }

            return Result.success("任务 " + taskToFinish.getId() + " 已完成，无人机 " + droneId + " 已归位");
        } catch (Exception e) {
            return Result.fail("结束任务失败: " + e.getMessage());
        }
    }
}
