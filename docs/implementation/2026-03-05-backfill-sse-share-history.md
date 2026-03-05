# SSE ETF 份额历史补录脚本 — 实现与运维手册

**日期**: 2026-03-05
**文件**: `backend/scripts/backfill_sse_share_history.py`

---

## 背景

系统每日 16:00 定时采集 SSE ETF 份额数据，存量记录从部署日起才有。本脚本用于**一次性手动补录**历史数据，SSE 官方 API 实测可追溯至 2020 年。

---

## 前置条件

数据库表必须已存在。若是全新部署，先运行：

```bash
cd backend && python3 scripts/init_share_history_table.py
```

> 脚本本身会在首次 DB 访问前自动调用 `create_share_history_tables()`（幂等），通常无需手动操作。

---

## 用法

```bash
# 补录指定日期范围（推荐加 --delay 1.0 防限流）
python3 scripts/backfill_sse_share_history.py --start 2020-01-01 --end 2026-03-04

# 仅补录某一天（功能验证）
python3 scripts/backfill_sse_share_history.py --start 2025-12-31 --end 2025-12-31

# dry-run：仅打印目标工作日，不写库
python3 scripts/backfill_sse_share_history.py --start 2025-01-01 --end 2025-01-31 --dry-run

# 自定义请求间隔（默认 1.0 秒）
python3 scripts/backfill_sse_share_history.py --start 2024-01-01 --end 2024-12-31 --delay 2.0
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--start` | 起始日期 YYYY-MM-DD | 必填 |
| `--end` | 结束日期 YYYY-MM-DD | 必填 |
| `--dry-run` | 仅打印目标日期，不请求也不写库 | False |
| `--delay` | 每次成功请求后等待秒数 | 1.0 |

---

## 运行时行为

1. 构建 ETF 白名单（Sina 列表，过滤债券 ETF）
2. 查询 DB 已有 SSE 日期集合，直接跳过（不发请求）
3. 对每个目标工作日（周一至周五）精确请求 SSE API
4. 非交易日（节假日）SSE 返回空列表，记为"非交易日跳过"
5. 请求失败最多重试 3 次（间隔 3 秒），仍失败记录到失败列表
6. 重复 `(code, date)` 通过 `IntegrityError` 静默跳过

### 汇总输出示例

```
============================================================
补录完成汇总
============================================================
  总工作日数：      261
  有效交易日数：    242
  已有数据跳过：    0
  非交易日跳过：    19
  请求失败日数：    0
  新增记录总数：    181,886
  重复跳过总数：    0
============================================================
```

---

## 预估运行时间

| 范围 | 工作日数 | 预估时间（delay=1.0s） |
|------|---------|----------------------|
| 1 个月 | ~22 天 | ~1 分钟 |
| 1 年 | ~242 天 | ~5 分钟 |
| 5 年（2020-2024） | ~1,200 天 | ~25 分钟 |
| 全量（2020-2026） | ~1,500 天 | ~30 分钟 |

> 实际时间取决于网络延迟和节假日数量。建议在业务低峰期运行。

---

## 幂等性

脚本可安全重复运行：
- 已有日期直接跳过（不发网络请求）
- 重复记录通过 `IntegrityError` 跳过（不报错）

---

## 查库验证

```bash
# 查看最近 5 个有数据的日期及记录数
sqlite3 backend/etf_share_history.db \
  "SELECT date, COUNT(*) FROM etf_share_history WHERE exchange='SSE' GROUP BY date ORDER BY date DESC LIMIT 5;"

# 查看总记录数
sqlite3 backend/etf_share_history.db \
  "SELECT COUNT(*) FROM etf_share_history WHERE exchange='SSE';"
```

---

## 数据格式

| 字段 | 来源 | 说明 |
|------|------|------|
| `code` | SSE `SEC_CODE` | 6 位 ETF 代码 |
| `date` | SSE `STAT_DATE` | YYYY-MM-DD |
| `shares` | SSE `TOT_VOL` ÷ 1e4 | 亿份（原始单位：万份） |
| `exchange` | 代码前缀推断 | 15/16/12 开头 → SZSE，其余 → SSE |
| `etf_type` | SSE `ETF_TYPE` | 如"股票型" |

---

## 相关文件

- 脚本：`backend/scripts/backfill_sse_share_history.py`
- 测试：`backend/tests/scripts/test_backfill_sse_share_history.py`
- 数据模型：`backend/app/models/etf_share_history.py`
- 数据库配置：`backend/app/core/share_history_database.py`
- 每日定时采集：`backend/app/services/fund_flow_collector.py`
- 表初始化脚本：`backend/scripts/init_share_history_table.py`
