# Phase 2 数据源抽象与 Baostock 集成设计

**创建日期**: 2026-02-16
**状态**: 已实施
**关联**: [数据源优化规划](../planning/data-source-optimization-plan.md)、[Baostock 评估报告](../research/baostock-evaluation.md)

---

## 1. 设计目标

将 2.1（Baostock 集成）和 2.2（降级策略优化）合并实施，通过抽象数据源接口统一管理历史数据获取，为阶段三的数据源多元化打好基础。

## 2. 架构设计

### 2.1 整体架构

```
                    ┌─────────────────────────┐
                    │   DataSourceManager      │
                    │   (配置驱动优先级 + 熔断) │
                    └────────────┬────────────┘
                                 │
                ┌────────────────┼────────────────┐
                ▼                ▼                ▼
      ┌──────────────┐  ┌───────────────┐  ┌──────────────┐
      │BaostockSource │  │EastMoneySource│  │  (未来扩展)   │
      │ (单例连接)     │  │ (现有 AkShare) │  │ Tushare etc. │
      └──────┬───────┘  └──────┬────────┘  └──────────────┘
             │                 │
      ┌──────────────────────────────────┐
      │   DataSourceMetrics (Phase 1)    │
      │   + CircuitBreaker 逻辑          │
      └──────────────────────────────────┘
```

### 2.2 降级链变更

**历史数据（优化后）**：
```
Baostock → AkShare EastMoney（无等待，立即降级）→ DiskCache(7d) → 过期缓存(永久)
```

**实时行情（不变）**：
```
EastMoney → Sina → THS → DiskCache → JSON
```

## 3. 核心组件

### 3.1 HistoryDataSource 协议

`backend/app/services/datasource_protocol.py`

定义统一接口，所有历史数据源实现：
- `name: str` — 数据源标识，用于 metrics 追踪
- `fetch_history(code, start_date, end_date, adjust) -> Optional[DataFrame]` — 返回统一格式 DataFrame
- `is_available() -> bool` — 连接状态检查

统一 DataFrame 格式：日期 / 开盘 / 最高 / 最低 / 收盘 / 成交量 / 成交额 / 涨跌幅

### 3.2 BaostockSource

`backend/app/services/baostock_service.py`

**连接管理**：单例模式，应用启动时 `bs.login()`，关闭时 `bs.logout()`。连接断开时自动重连（检测 error_code 后重试一次）。线程安全（`threading.Lock`）。

**ETF 代码转换**：基于代码前缀的完整映射规则：
- 上交所（sh）：5xxxxx、6xxxxx
- 深交所（sz）：0xxxxx、1xxxxx、3xxxxx

**数据格式**：Baostock 字段映射到项目统一格式，复权参数 `adjustflag="2"` 对应项目的 `qfq`。

### 3.3 EastMoneyHistorySource

从 `akshare_service.py` 的 `_fetch_history_eastmoney()` 抽取为独立类，实现 `HistoryDataSource` 协议。

变更：
- 重试次数从 3 次降为 1 次（manager 级别负责源切换）
- 去掉 60 秒重试等待

### 3.4 DataSourceManager

`backend/app/services/datasource_manager.py`

职责：
- 从配置读取数据源优先级列表
- 按优先级遍历，跳过被熔断的源
- 成功后写入 DiskCache，失败后继续下一个源
- 所有在线源失败后返回 None，由调用方走缓存兜底

### 3.5 熔断逻辑

扩展现有 `backend/app/core/metrics.py`，新增 `is_circuit_open(source)` 方法。

规则：
- 最近 N 次调用（默认 10 次）成功率 < 10% → 开启熔断，跳过该源
- 熔断持续时间：默认 5 分钟
- 到期后放行一次探测请求：成功 → 关闭熔断，失败 → 续期

基于 Phase 1 已有的 `DataSourceMetrics` 实现，零额外依赖。

## 4. 配置设计

扩展 `backend/app/core/config.py`（通过环境变量覆盖）：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `HISTORY_DATA_SOURCES` | `["baostock", "eastmoney"]` | 历史数据源优先级列表 |
| `BAOSTOCK_ENABLED` | `True` | Baostock 总开关（灰度/回滚） |
| `CIRCUIT_BREAKER_THRESHOLD` | `0.1` | 成功率低于此值触发熔断 |
| `CIRCUIT_BREAKER_WINDOW` | `10` | 熔断判断的最近调用次数 |
| `CIRCUIT_BREAKER_COOLDOWN` | `300` | 熔断冷却时间（秒） |

灰度发布通过修改 `BAOSTOCK_ENABLED` 和 `HISTORY_DATA_SOURCES` 配置实现，重启生效。

## 5. 对现有代码的改动

| 文件 | 改动 |
|------|------|
| `services/akshare_service.py` | `fetch_history_raw()` 委托给 DataSourceManager，保留缓存兜底逻辑 |
| `core/metrics.py` | 新增 `is_circuit_open()` 和熔断相关字段 |
| `core/config.py` | 新增数据源配置项 |

新建文件：
- `services/datasource_protocol.py`
- `services/baostock_service.py`
- `services/datasource_manager.py`
- `tests/test_baostock_service.py`
- `tests/test_datasource_manager.py`

## 6. 实施顺序

1. 定义协议 + 配置项
2. 实现 BaostockSource（单例连接 + 数据格式转换）
3. 抽取 EastMoneyHistorySource
4. 实现 DataSourceManager + 熔断逻辑
5. 修改 `fetch_history_raw()` 委托给 manager
6. 单元测试 + 数据一致性验证
7. 文档更新

## 7. 风险与回滚

- **回滚**：设置 `BAOSTOCK_ENABLED=False`，manager 自动跳过 Baostock，回到纯 EastMoney 链路
- **数据不一致风险**：实施阶段需自动化对比 Baostock 与 AkShare 的历史数据（前复权值、数据完整性）
- **Baostock 服务中断**：熔断器自动跳过，降级到 EastMoney

## 8. 成功指标

- 历史数据获取成功率 > 95%
- Baostock 成功率 > 90%
- AkShare 降级率 < 10%
- 平均响应时间 < 3 秒

---

**最后更新**: 2026-02-16
