# 常见问题与排障（FAQ）

## 1. 前端地图加载失败
现象：
- 页面提示“未配置 VITE_AMAP_KEY”或“AMap 加载失败”
排查：
- 检查 `frontend/.env.local` 是否存在且 Key 正确
- 检查网络是否可访问高德 JS SDK
- 重新启动前端（env 变更需重启）

## 2. AI 服务启动失败：找不到模型文件
现象：
- 控制台提示 best.pt / best_matcher.pt 路径不存在
原因：
- `ai-service/app.py` 中模型路径是硬编码的本机绝对路径
解决：
- 修改为你机器实际路径，或将权重放到对应路径

## 3. 后端启动失败：数据库连接错误
排查：
- `backend/src/main/resources/application.yml` 的 datasource 配置是否正确
- MySQL 是否启动，端口是否一致
- 数据库 `drone_inspection` 是否存在且已导入表结构

## 4. 上传图片成功但地图没有点位
可能原因：
- 图片无病害（模型检测结果为 0）
- AI 服务未启动或调用失败（inspection_image.status 可能为 FAILED）
- 地图瓦片缓存未刷新（可等待 TTL 或在后端增加清缓存操作）
建议排查路径：
- 查看 inspection_image 表的 status、error_msg
- 查看 defect_detail 是否写入
- 查看 defect_entity 是否产生（全局匹配后才会“转正”）

## 5. 结果图/原图打不开（404）
原因：
- 后端静态资源映射路径与实际保存目录不一致
- origin/result 目录不在配置路径中
解决：
- 修改 `application.yml` 的静态目录或 `WebConfig` 的 ResourceHandler
- 确保后端可访问 `http://localhost:8080/origin/...` 与 `/result/...`

## 6. 任务结束后没有触发全局匹配
说明：
- 全局匹配触发条件为：收到结束信号 + pendingImages=0
排查：
- 是否在“图片仍在处理”时就结束任务（需等待处理完成）
- AI 异步线程池是否异常（线程池配置/资源不足）

## 7. 安全与配置提醒
- 请在提交/公开前移除明文密码与地图 Key
- 推荐使用 `.env` 或外部配置注入敏感信息