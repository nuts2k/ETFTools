# API 接口参考

本文档提供 ETFTools 项目的完整 API 端点列表和说明。

## API 前缀

所有 API 端点均使用前缀 `/api/v1`

## API 端点列表

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | API 根端点（含版本信息） |
| `/health` | GET | 健康检查（含版本信息、数据就绪状态、数据源状态） |
| `/health/datasources` | GET | 数据源健康详情（各源成功率、延迟、状态） |
| `/etf/tags/popular` | GET | 获取搜索页热门标签列表 |
| `/etf/search?q={keyword}&tag={label}` | GET | 搜索 ETF（支持文本搜索或标签筛选，二选一） |
| `/etf/{code}/info` | GET | 获取实时基础信息（含交易状态） |
| `/etf/{code}/history` | GET | 获取 QFQ 历史数据 |
| `/etf/{code}/metrics` | GET | 获取核心指标 (CAGR, MDD, ATR, Volatility) |
| `/etf/batch-price?codes={codes}` | GET | 批量获取实时价格（轻量级，含交易状态） |
| `/watchlist` | GET | 获取云端自选列表 |
| `/watchlist/sync` | POST | 同步本地自选数据到云端（并集策略） |
| `/auth/token` | POST | 用户登录，获取 JWT |
| `/auth/register` | POST | 用户注册 |
| `/admin/users` | GET | 获取用户列表（管理员） |
| `/admin/users/{id}` | GET | 获取用户详情（管理员） |
| `/admin/users/{id}/toggle-admin` | POST | 切换管理员权限 |
| `/admin/users/{id}/toggle-active` | POST | 启用/禁用用户 |
| `/admin/system/config` | GET | 获取系统配置 |
| `/admin/system/config/registration` | POST | 开关用户注册 |
| `/admin/system/config/max-watchlist` | POST | 设置自选列表最大数量 |
| `/alerts/config` | GET | 获取告警配置 |
| `/alerts/config` | PUT | 更新告警配置（含每日摘要开关） |
| `/alerts/trigger` | POST | 手动触发告警检查 |
| `/alerts/trigger?summary=true` | POST | 手动触发每日摘要 |
| `/etf/compare?codes={codes}&period={period}` | GET | ETF 对比（归一化走势+相关性+对齐指标+温度） |
| `/etf/{code}/fund-flow` | GET | 获取 ETF 资金流向数据（份额规模、排名） |
| `/admin/fund-flow/collect` | POST | 手动触发份额采集（管理员） |
| `/admin/fund-flow/export` | POST | 导出份额历史 CSV（管理员） |

## 版本信息

`/` 和 `/api/v1/health` 端点返回 `version` 字段，格式遵循语义化版本规范（Semantic Versioning 2.0.0）。

---

**最后更新**: 2026-02-16
