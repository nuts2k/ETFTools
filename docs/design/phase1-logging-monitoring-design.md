# Phase 1 设计：日志系统优化 + 监控告警

**创建日期**: 2026-02-16
**状态**: 已批准，待实施
**关联**: [数据源优化规划](../planning/data-source-optimization-plan.md) 阶段一

## 背景

当前后端日志和监控现状：
- 日志：各模块各自 `logging.getLogger(__name__)`，无集中配置、无轮转、无结构化格式
- 监控：仅 `/api/v1/health` 基础端点，只检查 ETF 缓存是否初始化
- 指标：无任何数据源成功率、延迟等指标收集
- 告警：无系统级告警（用户级告警已有完整 Telegram 基础设施）

## 约束条件

- 部署环境：Docker 容器（生产），直接启动（开发）
- 日志输出：stdout（Docker logs 查看）
- 告警方式：复用现有 Telegram 通知服务，发送给已配置通知的管理员用户
- 监控量级：轻量内置（内存计数器），不引入 Prometheus 等外部依赖

## 设计方案

### 1.1 日志系统优化

**新建 `backend/app/core/logging_config.py`**

- 集中配置所有 logger，替代各模块散落的 `logging.basicConfig()`
- 格式：`[2026-02-16 15:30:01] [INFO] [akshare_service] Fetched 1515 ETFs from eastmoney (320ms)`
- 输出到 stdout（Docker 友好）
- 提供 `setup_logging()` 函数，在 `main.py` 启动时调用一次

**改动现有文件：**
- `main.py`：启动时调用 `setup_logging()`
- 删除各模块中的 `logging.basicConfig()` 调用

### 1.2 数据源指标收集器

**新建 `backend/app/core/metrics.py`**

```python
class DataSourceMetrics:  # 单例
    # 每个数据源独立追踪：
    #   success_count, failure_count
    #   latencies: deque(maxlen=100)  # 滑动窗口
    #   last_status: "ok" | "error"
    #   last_success_at, last_failure_at
    #   last_error_message

    def record_success(source, latency_ms): ...
    def record_failure(source, error, latency_ms): ...
    def get_success_rate(source) -> float: ...  # 最近100次的成功率
    def get_summary() -> dict: ...  # 所有数据源状态汇总
    def is_all_down() -> bool: ...  # 所有源都挂了？
```

**`@track_datasource` 装饰器：**
- 包裹数据源调用函数，自动计时、记录成功/失败、写日志
- 对现有代码只需加一行装饰器

### 1.3 增强健康端点

**新增 `GET /api/v1/health/datasources`**

```json
{
  "status": "degraded",
  "sources": {
    "eastmoney": {
      "status": "error",
      "success_rate": 0.0,
      "avg_latency_ms": null,
      "last_failure_at": "2026-02-16 15:30:01",
      "last_error": "Connection aborted"
    },
    "sina": {
      "status": "ok",
      "success_rate": 1.0,
      "avg_latency_ms": 850,
      "last_success_at": "2026-02-16 15:30:02"
    }
  }
}
```

整体 status 逻辑：所有源 ok → `healthy`，部分挂 → `degraded`，全挂 → `critical`

### 1.4 管理员告警广播

**新建 `backend/app/services/admin_alert_service.py`**

复用现有 `TelegramNotificationService`，新增：
- `send_admin_alert(alert_type, message)` — 查询所有 `is_admin=True` 且 Telegram 已验证的用户，逐个发送
- 防抖：同一 `alert_type` 5 分钟内不重复发送（内存字典记录上次发送时间）
- 告警类型：`all_sources_down`、`source_recovered`

**改动 `akshare_service.py`：**
- 将 EastMoney/Sina/THS 的获取逻辑拆成独立函数，加 `@track_datasource` 装饰器
- 在最终 fallback 分支触发 `send_admin_alert("all_sources_down", ...)`
- 当某个源从失败恢复时触发 `send_admin_alert("source_recovered", ...)`

## 文件变更总览

| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `app/core/logging_config.py` | 集中日志配置 |
| 新建 | `app/core/metrics.py` | DataSourceMetrics + @track_datasource 装饰器 |
| 新建 | `app/services/admin_alert_service.py` | 管理员 Telegram 广播 |
| 改动 | `app/main.py` | 调用 setup_logging()，新增健康端点 |
| 改动 | `app/services/akshare_service.py` | 拆分数据源函数 + 加装饰器 + 触发告警 |
| 新建 | `tests/test_metrics.py` | 指标收集器单元测试 |
| 新建 | `tests/test_admin_alert.py` | 管理员告警单元测试 |

## 不做的事情

- 不引入 structlog / python-json-logger（标准库够用）
- 不加 Prometheus（轻量内置）
- 不加日志轮转（Docker 自己管理）
- 不改现有的用户级告警逻辑（alert_scheduler.py 不动）

## 现有可复用基础设施

- `TelegramNotificationService`（`app/services/notification_service.py`）— 已有 send_message()、加密解密
- `User.settings["telegram"]` — 已有 botToken、chatId、enabled、verified 字段
- `User.is_admin` — 管理员标识
- `app/core/encryption.py` — Token 加密解密

---
**最后更新**: 2026-02-16
