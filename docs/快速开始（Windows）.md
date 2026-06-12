# 快速开始（Windows）

## 0. 前置条件
建议环境：
- Node.js：>= 20
- Java：17（与后端 pom.xml 保持一致）
- Python：3.10+（建议 3.10/3.11）
- MySQL：8.x
- Redis：6.x+

## 1. 数据库准备（MySQL）
1. 创建数据库（名称需与后端配置一致，默认 `drone_inspection`）。
2. 从 `db/` 目录选择一个 dump 文件导入（选择最新时间的即可）。

PowerShell 示例（需你自行替换账号密码）：
- 创建库：
  - `CREATE DATABASE drone_inspection DEFAULT CHARSET utf8mb4;`
- 导入：
  - 打开 MySQL 客户端执行：`source ...\UAVRoadDetection\db\xxx-dump.sql;`

## 2. 启动 Redis
确保 Redis 在 `localhost:6379` 可用（后端默认连接该地址）。

## 3. 启动 AI 服务（FastAPI）
进入目录：
- `cd ...\UAVRoadDetection\ai-service`

安装依赖：
- `python -m venv .venv`
- `.\.venv\Scripts\activate`
- `pip install -r requirements.txt`

启动：
- `python app.py`
或：
- `uvicorn app:app --host 0.0.0.0 --port 8000`

注意：
- AI 服务当前代码中存在模型权重与输出目录的“硬编码路径”，若与你机器不一致会启动失败，详见 `02-部署与配置.md`。

## 4. 启动后端（Spring Boot）
进入目录：
- `cd ...\UAVRoadDetection\backend`

启动：
- `.\mvnw.cmd spring-boot:run`

后端默认端口：
- `http://localhost:8080`

Swagger（通常可用其一）：
- `http://localhost:8080/swagger-ui/index.html`
- `http://localhost:8080/swagger-ui.html`

## 5. 启动前端（Vue3）
进入目录：
- `cd ...\UAVRoadDetection\frontend`

安装依赖并启动：
- `npm install`
- `npm run dev`

访问：
- `http://localhost:5173`

## 6. 最小可用验证（建议顺序）
1. 前端打开后进入“设备”页：新增无人机（名称任意）
2. 进入“任务”页：创建任务，绑定无人机，在地图点选航线点位，保存
3. 启动任务（任务状态变为执行中）
4. 通过无人机/模拟器上报图片（或后端接口测试工具调用上传接口）
5. 地图页刷新后看到病害点位（若模型识别到病害）
6. “采集控制台”连接 WebSocket，观察实时遥测/告警日志

## 7. 常见问题快速定位
- 前端地图加载失败：检查 `frontend/.env.local` 的高德 Key 与 SecurityJSCode
- 后端报数据库连接失败：检查 `backend/src/main/resources/application.yml` 的 MySQL 账号密码与库名
- AI 服务启动报找不到模型文件：检查 `ai-service/app.py` 内模型路径（硬编码）
- 地图点位不显示：可能无病害、或图片/病害未入库、或瓦片缓存未刷新（详见 08）