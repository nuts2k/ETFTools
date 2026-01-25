---
name: service-management
description: 当任务涉及启动、停止、重启后端或前端服务，或者需要检查服务运行状态时使用。必须通过 ./manage.sh 进行操作。
---

# Service Management (服务管理)

当任务涉及启动、停止、重启后端或前端服务，或者需要检查服务运行状态时，**必须**使用此 Skill。

## 核心原则
1. **统一入口**：严禁直接调用 `uvicorn` 或 `npm run dev`。必须始终使用项目根目录下的 `./manage.sh`。
2. **环境感知**：脚本会自动处理 `PYTHONPATH` 和虚拟环境。
3. **强制清理**：停止或重启服务时，脚本会处理僵尸进程和端口冲突，无需手动干预。

## 常用操作
- **启动/重启**：
  - `./manage.sh start` (标准启动)
  - `./manage.sh restart` (重启)
  - `./manage.sh restart --install` (当 `pyproject.toml` 或 `package.json` 发生变更时使用)
- **停止**：
  - `./manage.sh stop`
- **检查状态**：
  - `./manage.sh status`

## 故障排查
如果服务无法正常启动，请按以下顺序检查：
1. 运行 `./manage.sh status` 确认端口占用。
2. 查看后端日志：`tail -f backend/uvicorn.log`。
3. 查看前端日志：`tail -f frontend/nextjs.log`。
