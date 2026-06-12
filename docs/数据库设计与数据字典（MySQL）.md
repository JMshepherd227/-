# 数据库设计与数据字典（MySQL）

## 1. 数据库初始化
- 参考 `db/` 目录中的 dump 文件导入。
- 后端默认数据库名：`drone_inspection`（以 application.yml 为准）

## 2. 核心表说明（逻辑层）
说明：以下字段以代码实体类为口径，真实表字段以 dump 为准。

### 2.1 drone_device（无人机设备表）
对应实体：DroneDevice
- id：主键
- drone_name：无人机名称
- status：状态（如空闲/任务中等）
- last_lng / last_lat：最后位置
- create_time / update_time：时间戳

### 2.2 inspection_task（巡检任务表）
对应实体：InspectionTask
- id：主键
- task_name：任务名称
- drone_id：绑定无人机
- route_points：航线点位（JSON，列表结构）
- status：任务状态（未开始/执行中/已完成）
- defect_count：任务累计病害数
- create_time / update_time：时间戳

### 2.3 inspection_image（巡检图片表）
对应实体：InspectionImage
- id：主键
- task_id / drone_id：关联任务与无人机
- original_image_url：原图相对 URL（/origin/...）
- result_image_url：结果图相对 URL（/result/...）
- raw_lng / raw_lat：拍摄点经纬度
- matched_lng / matched_lat：匹配/贴合后的经纬度（如使用）
- is_defect：是否存在病害（1/0）
- defect_count：该图片病害数量
- status：处理状态（DONE/FAILED 等）
- error_msg：失败原因（如有）
- capture_time / create_time：时间戳

### 2.4 defect_entity（病害实体表）
对应实体：DefectEntity
- id：主键
- defect_type：病害类型（与模型类别映射有关）
- lng / lat：实体坐标（用于地图点位）
- status：状态（ACTIVE 等）
- create_time：创建时间

### 2.5 defect_detail（病害详情表）
对应实体：DefectDetail
- id：主键
- image_id：来源图片
- entity_id：关联 defect_entity（全局匹配后填充）
- temp_entity_id：任务内临时实体 ID（任务结束前用于汇聚）
- defect_type：类别名称（如“坑槽/裂缝”等）
- confidence：置信度
- bbox：边界框（JSON）
- feature_vector：特征向量（JSON，可用于后续检索/匹配）
- road_name/address/address_detail：逆地理编码补全字段
- create_time：时间戳

## 3. 数据口径说明（重要）
- “地图点位”来自 defect_entity（实体级）
- “识别列表/历史详情”来自 defect_detail（观测级，多次观测对应同一实体）
- temp_entity_id 用于任务执行过程中的临时聚合，任务结束后通过全局匹配转正为 entity_id