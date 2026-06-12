# 基于无人机的公路健康情况巡检系统开发

大创项目仓库。

项目成员：
- 组长：金枫凯（23301126）
- 组员：黄晨曦（23301123）
- 组员：黄冠宇（23301124）

## 项目结构

- `frontend/`：Vue 3 + Vite 前端
- `backend/`：Spring Boot 后端
- `ai-service/`：Python AI 推理与无人机场景相关服务
- `disease_matching/`：病害匹配与训练相关代码
- `docs/`：项目文档、部署说明、接口协议和测试清单
- `db/`：数据库导出与备份文件

## 快速启动

### 前端

```sh
cd frontend
npm install
npm run dev
```

### 后端

```sh
cd backend
./mvnw spring-boot:run
```

Windows 下可使用：

```sh
mvnw.cmd spring-boot:run
```

### AI 服务

```sh
cd ai-service
pip install -r requirements.txt
python app.py
```

## 文档入口

- `docs/项目概览.md`
- `docs/快速开始（Windows）.md`
- `docs/部署与配置说明.md`
- `docs/接口与消息协议.md`

## 说明

根目录原始 README 为前端模板文档，现已整理为项目总入口，便于整体提交与交付。
