# ETF 资金流向分析功能 - 实现计划

> 设计文档: [docs/design/2026-02-08-fund-flow-analysis-design.md](../design/2026-02-08-fund-flow-analysis-design.md)
> 创建时间: 2026-02-09
> 状态: 待实施

---

## 与设计文档的偏差

| # | 设计文档 | 实际实现 | 原因 |
|---|---------|---------|------|
| 1 | 使用 `schedule` 库做定时任务 | 使用 APScheduler | 复用现有 `alert_scheduler` 模式，不引入新依赖 |
| 2 | `created_at` 用 `datetime.now()` | 用 `datetime.utcnow()` | 遵循 AGENTS.md 4.5 强制规范 |
| 3 | 采集器和备份器各用独立线程 | 统一用 APScheduler 的 AsyncIOScheduler | 与 alert_scheduler 保持一致 |

---

## 改动文件总览

### 新建文件 (14个)

| # | 文件 | 说明 | Phase |
|---|------|------|-------|
| 1 | `backend/app/models/etf_share_history.py` | 数据模型 | 1 |
| 2 | `backend/app/core/share_history_database.py` | 独立数据库配置 | 1 |
| 3 | `backend/scripts/init_share_history_table.py` | 数据库初始化脚本 | 1 |
| 4 | `backend/app/services/fund_flow_collector.py` | 采集服务 + 调度器 | 2 |
| 5 | `backend/tests/services/test_fund_flow_collector.py` | 采集器单元测试 | 2 |
| 6 | `backend/app/services/fund_flow_service.py` | 业务逻辑服务 | 3 |
| 7 | `backend/app/services/fund_flow_cache_service.py` | 缓存服务 | 3 |
| 8 | `backend/tests/services/test_fund_flow_service.py` | 业务服务单元测试 | 3 |
| 9 | `backend/app/services/share_history_backup_service.py` | 备份服务 | 4 |
| 10 | `backend/tests/services/test_share_history_backup_service.py` | 备份服务单元测试 | 4 |
| 11 | `backend/tests/api/test_fund_flow_api.py` | API 集成测试 | 4 |
| 12 | `frontend/components/FundFlowCard.tsx` | 资金流向卡片组件 | 5 |
| 13 | `frontend/__tests__/FundFlowCard.test.tsx` | 前端组件测试 | 5 |

### 修改文件 (10个)

| # | 文件 | 改动类型 | 说明 | Phase |
|---|------|---------|------|-------|
| 1 | `backend/app/api/v1/endpoints/etf.py` | 新增端点 | `GET /{code}/fund-flow` | 4 |
| 2 | `backend/app/api/v1/endpoints/admin.py` | 新增端点 | 采集触发 + CSV 导出 | 4 |
| 3 | `backend/app/main.py` | 修改 | 启动/停止采集调度器 | 4 |
| 4 | `frontend/lib/api.ts` | 新增类型 | `FundFlowData` 接口 | 5 |
| 5 | `frontend/app/etf/[code]/page.tsx` | 修改 | 集成 FundFlowCard | 5 |
| 6 | `docker-compose.yml` | 修改 | 新增 volume 映射 | 6 |
| 7 | `Dockerfile` | 修改 | 新增 backups 目录 | 6 |
| 8 | `docker/entrypoint.sh` | 修改 | 新增数据库权限处理 | 6 |
| 9 | `AGENTS.md` | 修改 | 更新 API 速查表和代码导航 | 6 |
| 10 | `docs/planning/FEATURE-ROADMAP.md` | 修改 | 标记功能已实现 | 6 |

---

## Phase 1: 数据层（Model + Database + Init Script）

### Step 1.1: 创建数据模型

**新建**: `backend/app/models/etf_share_history.py`

**参考模式**: `backend/app/models/user.py` 中的 `Watchlist` 类

```python
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class ETFShareHistory(SQLModel, table=True):
    """ETF 份额历史记录表"""
    __tablename__ = "etf_share_history"
    __table_args__ = (
        UniqueConstraint('code', 'date', name='uq_code_date'),
        Index('idx_code_date', 'code', 'date'),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True)           # ETF代码，如 "510300"
    date: str = Field(index=True)           # 统计日期 YYYY-MM-DD
    shares: float                            # 基金份额（亿份）
    exchange: str                            # 交易所 "SSE" / "SZSE"
    etf_type: Optional[str] = None          # ETF类型，如 "股票型"
    created_at: datetime = Field(default_factory=datetime.utcnow)  # UTC!
```

**要点**:
- `code + date` 唯一约束防止重复采集
- `created_at` 使用 `datetime.utcnow`（AGENTS.md 4.5 强制规范）
- `shares` 单位为亿份，与 akshare 返回一致

---

### Step 1.2: 创建独立数据库配置

**新建**: `backend/app/core/share_history_database.py`

**参考模式**: `backend/app/core/database.py`

```python
import os
from sqlmodel import SQLModel, create_engine, Session

def _get_share_history_db_url() -> str:
    """构建独立数据库 URL，数据库文件位于 backend/ 目录"""
    backend_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    db_path = os.path.join(backend_dir, "etf_share_history.db")
    return f"sqlite:///{db_path}"

share_history_engine = create_engine(
    _get_share_history_db_url(),
    echo=False,
    connect_args={"check_same_thread": False}
)

def create_share_history_tables():
    """创建份额历史表（仅在独立数据库上创建）"""
    from app.models.etf_share_history import ETFShareHistory
    SQLModel.metadata.create_all(
        share_history_engine,
        tables=[ETFShareHistory.__table__]
    )

def get_share_history_session():
    """获取份额历史数据库会话（FastAPI DI 用）"""
    with Session(share_history_engine) as session:
        yield session
```

**关键**: 使用 `tables=[ETFShareHistory.__table__]` 参数，避免在独立数据库上创建所有 SQLModel 表。

---

### Step 1.3: 创建数据库初始化脚本

**新建**: `backend/scripts/init_share_history_table.py`

```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.share_history_database import create_share_history_tables

if __name__ == "__main__":
    create_share_history_tables()
    print("Table etf_share_history created in etf_share_history.db")
```

### Phase 1 验证

```bash
cd backend && python scripts/init_share_history_table.py
sqlite3 etf_share_history.db ".schema etf_share_history"
```

---

## Phase 2: 数据采集服务

### Step 2.1: 创建采集服务

**新建**: `backend/app/services/fund_flow_collector.py`

**参考模式**: `backend/app/services/alert_scheduler.py`（APScheduler 集成）

**类结构**: `FundFlowCollector`

**核心方法**:

1. `collect_daily_snapshot() -> Dict[str, Any]`
   - 主入口，依次采集上交所和深交所
   - 返回 `{"success": bool, "collected": int, "failed": int, "message": str}`

2. `_fetch_sse_shares() -> pd.DataFrame`
   - 调用 `ak.fund_etf_scale_sse()`
   - 返回原始 DataFrame

3. `_fetch_szse_shares() -> pd.DataFrame`
   - 调用 `ak.fund_etf_scale_szse()`
   - 返回原始 DataFrame

4. `_save_to_database(df: pd.DataFrame, exchange: str) -> int`
   - 标准化列名映射（见下方）
   - 逐行插入，UniqueConstraint 自动去重（捕获 IntegrityError 跳过）
   - 返回成功插入行数

5. `start()` / `stop()`
   - APScheduler 生命周期管理
   - 每日采集: 16:00 北京时间，周一至周五
   - 每月备份: 每月1号 02:00 北京时间

**数据标准化映射**:

```python
COLUMN_MAP = {
    "基金代码": "code",
    "基金份额(亿份)": "shares",    # 注意：akshare 列名可能有变化，需实际验证
    "统计日期": "date",
    "基金类型": "etf_type",
}
```

**APScheduler 集成**:

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo

def start(self) -> None:
    if self._scheduler is not None:
        return
    self._scheduler = AsyncIOScheduler()

    # 每日采集 16:00 北京时间
    self._scheduler.add_job(
        self._run_daily_collection,
        CronTrigger(
            hour=16, minute=0,
            day_of_week="mon-fri",
            timezone=ZoneInfo("Asia/Shanghai")
        ),
        id="fund_flow_daily_collection",
        replace_existing=True,
    )

    # 每月备份 每月1号 02:00
    self._scheduler.add_job(
        self._run_monthly_backup,
        CronTrigger(
            hour=2, minute=0, day=1,
            timezone=ZoneInfo("Asia/Shanghai")
        ),
        id="fund_flow_monthly_backup",
        replace_existing=True,
    )

    self._scheduler.start()

async def _run_daily_collection(self):
    await asyncio.to_thread(self.collect_daily_snapshot)

async def _run_monthly_backup(self):
    from app.services.share_history_backup_service import share_history_backup_service
    # 导出上个月数据
    ...
```

**全局单例**: `fund_flow_collector = FundFlowCollector()`

---

### Step 2.2: 创建采集器测试

**新建**: `backend/tests/services/test_fund_flow_collector.py`

**测试用例**:
- `test_fetch_sse_shares_success` — Mock `ak.fund_etf_scale_sse()`，验证返回 DataFrame
- `test_fetch_szse_shares_success` — Mock `ak.fund_etf_scale_szse()`
- `test_save_to_database` — 使用内存 SQLite，验证数据正确写入
- `test_save_to_database_dedup` — 插入相同数据两次，验证不重复
- `test_collect_daily_snapshot_partial_failure` — 一个交易所失败，另一个仍成功
- `test_collect_daily_snapshot_all_success` — 两个交易所都成功

**测试 fixture**: 需要创建内存数据库 engine + 样本 DataFrame

### Phase 2 验证

```bash
cd backend && pytest tests/services/test_fund_flow_collector.py -v
```

---

## Phase 3: 业务逻辑 + 缓存服务

### Step 3.1: 创建业务服务

**新建**: `backend/app/services/fund_flow_service.py`

**参考模式**: `backend/app/services/temperature_service.py`（计算服务模式）

**类结构**: `FundFlowService`

**核心方法**:

1. `get_current_scale(code: str) -> Optional[Dict]`
   - 查询 `etf_share_history` 表中该 ETF 最新记录（`ORDER BY date DESC LIMIT 1`）
   - 从 `etf_cache.get_etf_info(code)` 获取当前价格
   - 计算规模: `scale = shares × price`
   - 返回: `{"shares": float, "scale": float|None, "update_date": str, "exchange": str}`

2. `get_scale_rank(code: str) -> Optional[Dict]`
   - 先获取该 ETF 最新记录的日期
   - 查询同日期所有记录，按 `shares DESC` 排序
   - 找到该 ETF 的位置，计算百分位: `percentile = (total - rank + 1) / total * 100`
   - 返回: `{"rank": int, "total_count": int, "percentile": float, "category": str}`

3. `get_fund_flow_data(code: str) -> Optional[Dict]`
   - 组合 `get_current_scale` + `get_scale_rank`
   - 返回完整 API 响应结构（匹配设计文档 4.6 节）

**数据库访问**: 使用 `Session(share_history_engine)` 上下文管理器

**全局单例**: `fund_flow_service = FundFlowService()`

---

### Step 3.2: 创建缓存服务

**新建**: `backend/app/services/fund_flow_cache_service.py`

**参考模式**: `backend/app/services/temperature_cache_service.py`

**类结构**: `FundFlowCacheService`

```python
from app.services.akshare_service import disk_cache
from app.services.fund_flow_service import fund_flow_service

class FundFlowCacheService:
    CACHE_PREFIX = "fund_flow"
    CACHE_EXPIRE = 4 * 3600  # 4小时（秒）

    def _get_cache_key(self, code: str) -> str:
        return f"{self.CACHE_PREFIX}:{code}"

    def get_fund_flow(self, code: str, force_refresh: bool = False) -> Optional[Dict]:
        cache_key = self._get_cache_key(code)

        if not force_refresh:
            cached = disk_cache.get(cache_key)
            if cached is not None:
                return cached

        result = fund_flow_service.get_fund_flow_data(code)
        if result:
            disk_cache.set(cache_key, result, expire=self.CACHE_EXPIRE)
        return result

fund_flow_cache_service = FundFlowCacheService()
```

**与 temperature_cache_service 的区别**: 使用 TTL 过期（`expire=14400`），而非日期比对。因为份额数据每日更新一次，TTL 更简单。

---

### Step 3.3: 创建业务服务测试

**新建**: `backend/tests/services/test_fund_flow_service.py`

**测试用例**:
- `test_get_current_scale_with_data` — 数据库有记录时返回正确的份额和规模
- `test_get_current_scale_no_data` — 数据库无记录时返回 None
- `test_get_current_scale_no_price` — 有份额但无法获取价格时，scale 为 None
- `test_get_scale_rank` — 验证排名和百分位计算正确性
- `test_get_scale_rank_single_etf` — 只有一只 ETF 时排名为 1
- `test_cache_hit` — 缓存命中时不调用 service
- `test_cache_miss` — 缓存未命中时调用 service 并写入缓存
- `test_force_refresh` — force_refresh=True 时跳过缓存

**测试 fixture**: Mock `share_history_engine` 和 `etf_cache`

### Phase 3 验证

```bash
cd backend && pytest tests/services/test_fund_flow_service.py -v
```

---

## Phase 4: API 端点 + 备份服务 + 启动集成

### Step 4.1: 添加 fund-flow API 端点

**修改**: `backend/app/api/v1/endpoints/etf.py`

**参考**: 同文件中 `get_etf_metrics` 端点（约第 134 行）

在文件末尾新增：

```python
from app.services.fund_flow_cache_service import fund_flow_cache_service

@router.get("/{code}/fund-flow")
async def get_fund_flow(code: str, force_refresh: bool = False):
    """获取 ETF 资金流向数据（份额规模、排名）"""
    result = fund_flow_cache_service.get_fund_flow(code, force_refresh=force_refresh)
    if not result:
        raise HTTPException(
            status_code=404,
            detail="No fund flow data available for this ETF"
        )
    return result
```

---

### Step 4.2: 添加管理员端点

**修改**: `backend/app/api/v1/endpoints/admin.py`

**参考**: 同文件中 `toggle_admin_status` 端点（第 45 行）

在文件末尾新增两个端点：

**端点 1: 手动触发采集**

```python
import asyncio
from app.services.fund_flow_collector import fund_flow_collector

@router.post("/fund-flow/collect")
async def trigger_fund_flow_collection(
    admin: User = Depends(get_current_admin_user)
):
    """手动触发 ETF 份额数据采集（管理员）"""
    result = await asyncio.to_thread(fund_flow_collector.collect_daily_snapshot)
    return result
```

**端点 2: 导出 CSV**

```python
from fastapi import Query
from fastapi.responses import StreamingResponse
from app.services.share_history_backup_service import share_history_backup_service
import io

@router.post("/fund-flow/export")
async def export_share_history(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    admin: User = Depends(get_current_admin_user)
):
    """导出份额历史数据为 CSV（管理员）"""
    csv_bytes = share_history_backup_service.export_to_csv_bytes(
        start_date, end_date
    )
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={
            "Content-Disposition":
                f"attachment; filename=etf_share_history_{start_date}_{end_date}.csv"
        }
    )
```

---

### Step 4.3: 创建备份服务

**新建**: `backend/app/services/share_history_backup_service.py`

**类结构**: `ShareHistoryBackupService`

**核心方法**:

1. `export_to_csv_bytes(start_date, end_date, codes=None) -> bytes`
   - 查询指定日期范围的记录
   - 用 `pandas.DataFrame.to_csv()` 转为 CSV bytes
   - 供 admin API 端点使用

2. `export_monthly_backup(year, month) -> Dict`
   - 导出指定月份数据到文件
   - 文件路径: `backups/share_history/etf_share_history_YYYY-MM.csv`
   - 自动创建备份目录
   - 供定时任务调用

**备份目录**: `backend/backups/share_history/`（相对于 backend 目录）

**全局单例**: `share_history_backup_service = ShareHistoryBackupService()`

---

### Step 4.4: 创建备份服务测试

**新建**: `backend/tests/services/test_share_history_backup_service.py`

**测试用例**:
- `test_export_to_csv_bytes_with_data` — 有数据时返回正确 CSV 内容
- `test_export_to_csv_bytes_empty` — 无数据时返回空 CSV（仅表头）
- `test_export_monthly_backup_creates_file` — 验证文件创建和内容
- `test_backup_directory_auto_creation` — 备份目录不存在时自动创建

---

### Step 4.5: 创建 API 集成测试

**新建**: `backend/tests/api/test_fund_flow_api.py`

**参考模式**: `backend/tests/api/test_etf_api.py`

**测试用例**:
- `test_get_fund_flow_success` — 有数据时返回 200 + 正确结构
- `test_get_fund_flow_not_found` — 无数据时返回 404
- `test_get_fund_flow_force_refresh` — force_refresh 参数传递正确
- `test_admin_collect_requires_auth` — 未认证时返回 401
- `test_admin_collect_requires_admin` — 普通用户返回 403
- `test_admin_collect_success` — 管理员触发采集成功
- `test_admin_export_csv` — 管理员导出 CSV 返回正确 content-type

---

### Step 4.6: 集成到应用生命周期

**修改**: `backend/app/main.py`

**参考**: 同文件中 `alert_scheduler.start()` / `alert_scheduler.stop()`（第 44-51 行）

**新增 import**（文件顶部）:

```python
from app.core.share_history_database import create_share_history_tables
from app.services.fund_flow_collector import fund_flow_collector
```

**修改 lifespan 函数**:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    create_db_and_tables()
    create_share_history_tables()          # 新增
    init_admin_from_env()
    # ... 现有代码 ...
    alert_scheduler.start()
    fund_flow_collector.start()            # 新增
    logger.info("Fund flow collector scheduler started.")

    yield

    # Shutdown
    alert_scheduler.stop()
    fund_flow_collector.stop()             # 新增
    logger.info("Fund flow collector scheduler stopped.")
```

### Phase 4 验证

```bash
cd backend && pytest tests/ -v
# 启动服务器后手动测试
curl -X POST http://localhost:8000/api/v1/admin/fund-flow/collect \
  -H "Authorization: Bearer $TOKEN"
curl http://localhost:8000/api/v1/etf/510300/fund-flow | python -m json.tool
```

---

## Phase 5: 前端实现

### Step 5.1: 添加类型定义

**修改**: `frontend/lib/api.ts`

在 `GridSuggestion` 接口（第 124 行）之后新增：

```typescript
// 资金流向数据
export interface FundFlowData {
  code: string;
  name: string;
  current_scale: {
    shares: number;      // 亿份
    scale: number | null; // 亿元
    update_date: string;
    exchange: string;
  };
  rank: {
    rank: number;
    total_count: number;
    percentile: number;
    category: string;
  } | null;
  historical_available: boolean;
  data_points: number;
}
```

---

### Step 5.2: 创建 FundFlowCard 组件

**新建**: `frontend/components/FundFlowCard.tsx`

**参考模式**: `frontend/components/TrendAnalysisCard.tsx`（三态卡片模式）

**Props 接口**:

```typescript
interface FundFlowCardProps {
  data: FundFlowData | null;
  isLoading: boolean;
}
```

**三态处理**:

1. **Loading 态**: 渲染 skeleton（`animate-pulse` 占位）
2. **无数据态**: `return null`（不渲染）
3. **正常态**: 展示份额、规模、排名、百分位

**UI 布局**（参考设计文档 5.2 节）:

```
┌─────────────────────────────────────┐
│ 资金流向                            │  ← Header
├─────────────────────────────────────┤
│ 当前规模                            │
│   910.62 亿份                       │  ← 主数据
│   3,578.54 亿元                     │
│                                     │
│ 规模排名                            │
│   第 3 名 / 593 只                  │
│   超过 99.5% 的股票型ETF            │
├─────────────────────────────────────┤
│ 数据日期: 2025-01-15               │  ← Footer
└─────────────────────────────────────┘
```

**样式规范**:
- 容器: `bg-card rounded-xl p-4 shadow-sm border border-border`
- 标题: `text-sm font-medium text-muted-foreground`
- 主数值: `text-2xl font-bold`
- 副数值: `text-lg text-muted-foreground`
- Footer: `text-[10px] text-muted-foreground/60`

---

### Step 5.3: 集成到详情页

**修改**: `frontend/app/etf/[code]/page.tsx`

**新增 import**（文件顶部）:

```typescript
import FundFlowCard from "@/components/FundFlowCard";
import { type FundFlowData } from "@/lib/api";
```

**新增 state**（约第 35 行，在 `gridSuggestion` state 之后）:

```typescript
const [fundFlow, setFundFlow] = useState<FundFlowData | null>(null);
const [fundFlowLoading, setFundFlowLoading] = useState(false);
```

**新增 useEffect**（约第 105 行，在 gridSuggestion useEffect 之后）:

```typescript
useEffect(() => {
  async function loadFundFlow() {
    if (!code) return;
    try {
      setFundFlowLoading(true);
      const data = await fetchClient<FundFlowData>(`/etf/${code}/fund-flow`);
      setFundFlow(data);
    } catch (err) {
      console.error("Failed to load fund flow", err);
    } finally {
      setFundFlowLoading(false);
    }
  }
  loadFundFlow();
}, [code]);
```

**渲染位置**（在 TrendAnalysisCard 和 GridSuggestionCard 之间，约第 268 行）:

```tsx
{/* Fund Flow Card */}
<div className="mb-6">
  <FundFlowCard
    data={fundFlow}
    isLoading={fundFlowLoading}
  />
</div>
```

---

### Step 5.4: 创建组件测试

**新建**: `frontend/__tests__/FundFlowCard.test.tsx`

**参考模式**: 现有前端测试文件

**测试用例**:
- `test_renders_skeleton_when_loading` — isLoading=true 时渲染 skeleton
- `test_returns_null_when_no_data` — data=null 且 isLoading=false 时不渲染
- `test_renders_shares_and_scale` — 正常数据展示份额和规模
- `test_renders_rank_info` — 展示排名和百分位
- `test_renders_without_rank` — rank 为 null 时仍正常渲染
- `test_renders_update_date` — Footer 展示数据日期

### Phase 5 验证

```bash
cd frontend && npx vitest run __tests__/FundFlowCard.test.tsx
```

---

## Phase 6: Docker + 文档更新

### Step 6.1: 更新 Docker 配置

**修改**: `docker-compose.yml`

在 `volumes` 部分新增两行：

```yaml
volumes:
  - ./data/etftool.db:/app/backend/etftool.db
  - ./data/etf_share_history.db:/app/backend/etf_share_history.db  # 新增
  - ./data/backups:/app/backend/backups                            # 新增
  - ./data/cache:/app/backend/cache
  - ./data/logs:/var/log/supervisor
```

**修改**: `Dockerfile`

在 `RUN mkdir -p` 行（约第 72 行）新增 backups 目录：

```dockerfile
RUN mkdir -p /app/backend/cache /app/backend/logs /app/backend/backups /var/log/supervisor
```

**修改**: `docker/entrypoint.sh`

1. 新增份额历史数据库的权限处理（在现有 `DB_FILE` 处理逻辑之后）：

```bash
# 份额历史数据库文件
SHARE_DB_FILE="/app/backend/etf_share_history.db"
if [ -f "$SHARE_DB_FILE" ]; then
    if [ ! -w "$SHARE_DB_FILE" ]; then
        chown www-data:www-data "$SHARE_DB_FILE" 2>/dev/null
        chmod 660 "$SHARE_DB_FILE" 2>/dev/null
    fi
fi
```

2. 在 `mkdir -p` 行新增 backups 目录：

```bash
mkdir -p /app/backend/cache /app/backend/logs /app/backend/backups /var/log/supervisor
chown -R www-data:www-data /app/backend/cache /app/backend/logs /app/backend/backups /var/log/supervisor
```

---

### Step 6.2: 更新 AGENTS.md

**修改**: `AGENTS.md`

**更新内容**:

1. **API 接口速查表**新增：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/etf/{code}/fund-flow` | GET | 获取 ETF 资金流向数据 |
| `/admin/fund-flow/collect` | POST | 手动触发份额采集（管理员） |
| `/admin/fund-flow/export` | POST | 导出份额历史 CSV（管理员） |

2. **核心代码导航**新增：
   - `backend/app/models/etf_share_history.py` — 份额历史数据模型
   - `backend/app/core/share_history_database.py` — 独立数据库配置
   - `backend/app/services/fund_flow_collector.py` — 采集服务 + 调度器
   - `backend/app/services/fund_flow_service.py` — 业务逻辑
   - `backend/app/services/fund_flow_cache_service.py` — 缓存服务
   - `backend/app/services/share_history_backup_service.py` — 备份服务
   - `frontend/components/FundFlowCard.tsx` — 资金流向卡片

3. **配置文件部分**新增：
   - `etf_share_history.db` — 独立份额历史数据库
   - `backups/share_history/` — 份额历史备份目录

---

### Step 6.3: 更新功能路线图

**修改**: `docs/planning/FEATURE-ROADMAP.md`

将资金流向分析功能标记为"阶段1已实现"。

---

### Step 6.4: 更新设计文档状态

**修改**: `docs/design/2026-02-08-fund-flow-analysis-design.md`

将文档头部状态从 `待实现` 改为 `阶段1已实现`。

---

### Step 6.5: 更新文档索引

**修改**: `docs/README.md`

在 `design/` 文档列表中新增：
```
- `2026-02-08-fund-flow-analysis-design.md` - ETF 资金流向分析设计
```

在 `implementation/` 文档列表中新增：
```
- `2026-02-09-fund-flow-analysis-impl.md` - ETF 资金流向分析实现
```

### Phase 6 验证

```bash
# Docker 构建验证
docker compose build
# 文档链接检查
ls docs/design/2026-02-08-fund-flow-analysis-design.md
ls docs/implementation/2026-02-09-fund-flow-analysis-impl.md
```

---

## 端到端验证流程

完成所有 Phase 后，按以下顺序验证：

```bash
# 1. 后端测试
cd backend && pytest tests/ -v

# 2. 前端测试
cd frontend && npx vitest run

# 3. 启动服务
cd .. && ./manage.sh start

# 4. 手动触发采集（需先获取管理员 token）
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/token \
  -d "username=admin&password=admin123" | python -m json.tool | grep access_token)
curl -X POST http://localhost:8000/api/v1/admin/fund-flow/collect \
  -H "Authorization: Bearer $TOKEN"

# 5. 测试 API
curl http://localhost:8000/api/v1/etf/510300/fund-flow | python -m json.tool

# 6. 浏览器验证
# 打开 http://localhost:3000 → 搜索 510300 → 检查资金流向卡片
```
