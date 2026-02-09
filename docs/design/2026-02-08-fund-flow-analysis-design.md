# ETF 资金流向分析功能 - 设计文档

> 创建时间: 2026-02-08
> 状态: 阶段1已实现
> 优先级: P1（高价值，需要一定开发投入）

---

## 1. 功能定位

### 1.1 为什么需要这个功能？

根据 `docs/planning/FEATURE-ROADMAP.md` 的规划，资金流向分析是 P1 优先级功能，具有以下价值：

- **用户价值**：ETF 独有的分析视角，申购赎回数据能反映机构资金动向
- **差异化竞争力**：市面上大多数 ETF 工具只提供价格走势，缺少份额规模分析
- **投资决策辅助**：大规模 ETF 通常流动性更好，份额增长反映市场认可度

### 1.2 核心价值主张

**为投资者提供"资金用脚投票"的视角**

- 价格涨跌可能受短期情绪影响，但份额变动反映真实资金流向
- 大规模持续流入的 ETF 往往代表市场共识
- 份额规模是流动性的重要指标

---

## 2. 数据源分析

### 2.1 akshare 接口调研

经过深入研究（参考 Explore Agent a2d063c 的报告），akshare 提供以下接口：

| 接口 | 数据内容 | 历史数据 | 可用性 | 数据量 |
|------|---------|---------|--------|--------|
| `fund_etf_scale_sse` | 上交所 ETF 份额快照 | ❌ 无 | ✅ 可用 | 593只 |
| `fund_etf_scale_szse` | 深交所 ETF 份额快照 | ❌ 无 | ✅ 可用 | 912只 |
| `fund_scale_change_em` | 全市场季度资金流向 | ✅ 27年 | ⚠️ 无单只明细 | 汇总数据 |

### 2.2 关键限制

**无法直接获取单只 ETF 的历史份额变动数据**

- akshare 只提供当前快照，不提供历史时间序列
- 东方财富的季度数据是汇总统计，无单只 ETF 明细
- 需要自建数据采集系统，定期抓取快照并存储

### 2.3 数据字段说明

**上交所数据示例**（`fund_etf_scale_sse`）：
```python
{
    '基金代码': '510300',
    '基金简称': '300ETF',
    '基金类型': '股票型',
    '基金份额(亿份)': 910.62,
    '统计日期': '2025-01-15'
}
```

**深交所数据示例**（`fund_etf_scale_szse`）：
```python
{
    '基金代码': '159915',
    '基金简称': '创业板ETF',
    '基金类型': '股票型',
    '基金份额(亿份)': 456.78,
    '统计日期': '2025-01-15'
}
```

---

## 3. 解决方案

### 3.1 分阶段实现策略

由于数据源限制，采用**分阶段实现**：

#### 阶段 1（本次实现）：基础份额展示

**目标**：显示当前份额规模和排名

**功能**：
- 展示当前份额规模（亿份）
- 计算总规模（份额 × 净值）
- 显示规模排名和百分位
- 建立后台定时采集系统

**数据积累**：为未来趋势分析打基础

#### 阶段 2（未来扩展）：趋势分析

**前置条件**：积累至少 30 天历史数据

**功能**：
- 份额变动趋势图（折线图）
- 净申购/赎回计算
- 大额事件标注（单日变动 >5%）
- 资金流向强度指标

### 3.2 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                    前端展示层                            │
│  FundFlowCard.tsx - 资金流向卡片组件                    │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                    API 层                                │
│  GET /api/v1/etf/{code}/fund-flow                       │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                 业务逻辑层                               │
│  FundFlowService - 规模查询、排名计算                   │
│  FundFlowCacheService - 缓存管理（4h过期）              │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                 数据采集层                               │
│  FundFlowCollector - 定时采集（每日16:00）              │
│    ├── fetch_sse_shares() - 上交所数据                  │
│    └── fetch_szse_shares() - 深交所数据                 │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                 数据存储层                               │
│  etf_share_history 表 - 份额历史记录                    │
│    ├── code (索引)                                      │
│    ├── date (索引)                                      │
│    ├── shares (份额)                                    │
│    └── exchange (交易所)                                │
└─────────────────────────────────────────────────────────┘
```

### 3.3 数据流设计

**采集流程**：
```
16:00 定时触发
  → 调用 akshare API
  → 数据清洗和标准化
  → 存储到数据库（自动去重）
  → 记录日志
```

**查询流程**：
```
用户请求
  → 检查缓存（4h有效期）
  → 缓存未命中 → 查询数据库
  → 计算规模和排名
  → 写入缓存
  → 返回结果
```

---

## 4. 后端实现方案

### 4.1 数据模型与数据库分离

**设计决策：使用独立数据库文件**

历史份额数据具有长期价值，适合独立管理：
- **数据库文件**：`etf_share_history.db`（独立于主业务数据库 `etf_tool.db`）
- **理由**：
  - 历史数据具有长期价值，适合独立管理和备份
  - 便于跨项目共享和数据迁移
  - 避免与业务数据混在一起，降低耦合度
- **数据量预估**：1505只 ETF × 365天 × 5年 ≈ 270万条记录（约 500MB）

**新建文件**：`backend/app/models/etf_share_history.py`

```python
from sqlmodel import SQLModel, Field, UniqueConstraint, Index
from typing import Optional
from datetime import datetime

class ETFShareHistory(SQLModel, table=True):
    """ETF 份额历史记录表"""
    __tablename__ = "etf_share_history"

    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True)  # ETF代码
    date: str = Field(index=True)  # 统计日期 YYYY-MM-DD
    shares: float  # 基金份额（份）
    exchange: str  # 交易所 SSE/SZSE
    etf_type: Optional[str] = None  # ETF类型
    created_at: datetime = Field(default_factory=datetime.now)

    __table_args__ = (
        UniqueConstraint('code', 'date', name='uq_code_date'),
        Index('idx_code_date', 'code', 'date'),
    )
```

**设计要点**：
- `code + date` 唯一约束，防止重复采集
- 双字段索引优化查询性能
- `exchange` 字段区分上交所/深交所
- `created_at` 记录数据入库时间

**新建文件**：`backend/app/core/share_history_database.py`

```python
from sqlmodel import create_engine, Session
import os

# 独立的数据库文件路径
SHARE_HISTORY_DB_PATH = os.path.join(os.getcwd(), "etf_share_history.db")
SHARE_HISTORY_DB_URL = f"sqlite:///{SHARE_HISTORY_DB_PATH}"

# 创建独立的数据库引擎
share_history_engine = create_engine(
    SHARE_HISTORY_DB_URL,
    echo=False,
    connect_args={"check_same_thread": False}
)

def get_share_history_session():
    """获取份额历史数据库会话"""
    with Session(share_history_engine) as session:
        yield session
```

**数据库初始化脚本**：`backend/scripts/init_share_history_table.py`

```python
from app.core.share_history_database import share_history_engine
from app.models.etf_share_history import ETFShareHistory
from sqlmodel import SQLModel

def init_table():
    """创建 etf_share_history 表（独立数据库）"""
    SQLModel.metadata.create_all(share_history_engine)
    print("✓ Table etf_share_history created in etf_share_history.db")

if __name__ == "__main__":
    init_table()
```

### 4.2 数据采集服务

**新建文件**：`backend/app/services/fund_flow_collector.py`

**采集范围说明**：
- **采集所有 ETF**：调用 `fund_etf_scale_sse` 和 `fund_etf_scale_szse` 获取所有返回的数据
- **预计数量**：上交所 593只 + 深交所 912只 ≈ 1505只
- **存储策略**：全量存储，通过定期清理（保留2年）控制存储空间
- **数据一致性**：采集的数据可能包含系统中未被查询过的 ETF，这是正常的，为未来扩展预留数据

**核心功能**：
- 定时采集上交所/深交所 ETF 份额快照
- 数据清洗和标准化
- 存储到数据库（自动去重）
- 错误处理和日志记录

**关键方法**：

```python
class FundFlowCollector:
    def collect_daily_snapshot(self) -> Dict[str, Any]:
        """
        每日采集任务入口

        返回: {
            "success": bool,
            "collected": int,  # 成功采集的记录数
            "failed": int,     # 失败的记录数
            "message": str
        }
        """

    def _fetch_sse_shares(self) -> pd.DataFrame:
        """获取上交所份额数据"""

    def _fetch_szse_shares(self) -> pd.DataFrame:
        """获取深交所份额数据"""

    def _save_to_database(self, df: pd.DataFrame, exchange: str) -> int:
        """保存到数据库，返回成功插入的行数"""

    def start_scheduler(self):
        """启动定时调度器（每日16:00执行）"""

    def stop_scheduler(self):
        """停止调度器"""
```

**调度策略**：
- 使用 `schedule` 库实现定时任务
- 每日 16:00 执行（收盘后，数据已更新）
- 失败重试：间隔 5 分钟，最多 3 次
- 独立线程运行，不阻塞主进程

### 4.3 数据备份服务

**设计目标**：
- 历史份额数据具有长期价值，需要可靠的备份机制
- 支持数据导出，便于跨项目共享和数据分析
- 提供管理员接口，支持按需导出

**新建文件**：`backend/app/services/share_history_backup_service.py`

**核心功能**：

1. **定期自动导出**：
   - 每月 1 号凌晨 2:00 自动导出上月数据
   - 导出格式：CSV
   - 文件命名：`etf_share_history_YYYY-MM.csv`
   - 存储路径：`backups/share_history/`

2. **手动导出（管理员）**：
   - 支持指定时间范围导出
   - 支持导出格式选择（CSV/JSON）
   - 支持按 ETF 代码过滤导出

**关键方法**：

```python
class ShareHistoryBackupService:
    def export_to_csv(
        self,
        start_date: str,
        end_date: str,
        output_path: str,
        codes: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        导出历史数据为 CSV

        参数:
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            output_path: 输出文件路径
            codes: ETF 代码列表（可选，为空则导出所有）

        返回: {
            "success": bool,
            "file_path": str,
            "records": int,
            "file_size": str
        }
        """

    def export_monthly_backup(self, year: int, month: int) -> Dict[str, Any]:
        """导出指定月份的数据（定期任务调用）"""

    def start_backup_scheduler(self):
        """启动备份调度器（每月1号凌晨2:00执行）"""

    def stop_backup_scheduler(self):
        """停止备份调度器"""
```

**备份目录结构**：
```
backups/
└── share_history/
    ├── etf_share_history_2026-01.csv
    ├── etf_share_history_2026-02.csv
    └── ...
```

### 4.4 核心业务服务

**新建文件**：`backend/app/services/fund_flow_service.py`

**核心功能**：
- 查询单只 ETF 的当前份额规模
- 计算规模排名和百分位
- 计算总规模（份额 × 净值）

**关键方法**：

```python
class FundFlowService:
    def get_current_scale(self, code: str) -> Optional[Dict]:
        """
        获取当前份额规模

        返回: {
            "shares": float,      # 份额（亿份）
            "scale": float,       # 规模（亿元）
            "update_date": str,   # 更新日期
            "exchange": str       # 交易所
        }
        """

    def get_scale_rank(self, code: str) -> Optional[Dict]:
        """
        获取规模排名

        返回: {
            "rank": int,          # 排名
            "total_count": int,   # 总数
            "percentile": float,  # 百分位
            "category": str       # 分类
        }
        """
```

### 4.5 缓存服务

**新建文件**：`backend/app/services/fund_flow_cache_service.py`

遵循现有缓存服务模式（参考 `temperature_cache_service.py`）：
- 使用 DiskCache，4小时过期
- 支持 `force_refresh` 参数
- 线程安全

### 4.6 API 端点

**修改文件**：`backend/app/api/v1/endpoints/etf.py`

新增端点：

```python
@router.get("/{code}/fund-flow")
async def get_fund_flow(code: str, force_refresh: bool = False):
    """
    获取 ETF 资金流向数据

    响应示例：
    {
      "code": "510300",
      "name": "300ETF",
      "current_scale": {
        "shares": 910.62,  // 亿份
        "scale": 3578.54,  // 亿元
        "update_date": "2025-01-15",
        "exchange": "SSE"
      },
      "rank": {
        "rank": 3,
        "total_count": 593,
        "percentile": 99.5,
        "category": "股票型ETF"
      },
      "historical_available": false,
      "data_points": 0
    }
    """
```

**修改文件**：`backend/app/api/v1/endpoints/admin.py`

新增管理员端点：

1. **手动触发采集**：
```python
@router.post("/fund-flow/collect")
async def trigger_collection(current_user: User = Depends(get_current_admin)):
    """手动触发份额数据采集（管理员）"""
```

2. **手动导出备份**：
```python
@router.post("/fund-flow/export")
async def export_share_history(
    start_date: str,
    end_date: str,
    format: str = "csv",
    codes: Optional[List[str]] = None,
    current_user: User = Depends(get_current_admin)
):
    """
    手动导出份额历史数据（管理员）

    参数:
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD
        format: 导出格式 csv/json
        codes: ETF代码列表（可选）

    返回: 文件下载响应
    """
```

### 4.7 定时任务集成

**修改文件**：`backend/app/main.py`

在 `lifespan` 函数中启动采集调度器和备份调度器：

```python
from app.services.fund_flow_collector import fund_flow_collector
from app.services.share_history_backup_service import share_history_backup_service

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动资金流向采集调度器
    collector_thread = threading.Thread(
        target=fund_flow_collector.start_scheduler,
        daemon=True
    )
    collector_thread.start()
    logger.info("Fund flow collector scheduler started")

    # 启动备份调度器
    backup_thread = threading.Thread(
        target=share_history_backup_service.start_backup_scheduler,
        daemon=True
    )
    backup_thread.start()
    logger.info("Share history backup scheduler started")

    yield

    fund_flow_collector.stop_scheduler()
    share_history_backup_service.stop_backup_scheduler()
```

---

## 5. 前端实现方案

### 5.1 类型定义

**修改文件**：`frontend/lib/api.ts`

新增类型：

```typescript
export interface FundFlowData {
  code: string;
  name: string;
  current_scale: {
    shares: number;
    scale: number;
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

### 5.2 资金流向卡片组件

**新建文件**：`frontend/components/FundFlowCard.tsx`

**UI 设计**（遵循现有卡片模式）：

```
┌─────────────────────────────────────┐
│ 资金流向                    [?]     │  ← Header
├─────────────────────────────────────┤
│ 当前规模                            │
│   910.62 亿份                       │  ← Content
│   3,578.54 亿元                     │
│                                     │
│ 规模排名                            │
│   第 3 名 / 593 只                  │
│   超过 99.5% 的股票型ETF            │
├─────────────────────────────────────┤
│ 数据日期: 2025-01-15               │  ← Footer
└─────────────────────────────────────┘
```

**关键特性**：
- 加载状态：Skeleton 占位屏
- 无数据状态：返回 null（不渲染）
- Tooltip：解释份额规模的含义
- 响应式：Mobile-first 设计

### 5.3 集成到详情页

**修改文件**：`frontend/app/etf/[code]/page.tsx`

**集成位置**：在 `TrendAnalysisCard` 和 `GridSuggestionCard` 之间

**新增代码**：

```typescript
// 状态管理
const [fundFlow, setFundFlow] = useState<FundFlowData | null>(null);
const [fundFlowLoading, setFundFlowLoading] = useState(false);

// 数据加载
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

// 渲染
<FundFlowCard
  code={code}
  data={fundFlow}
  isLoading={fundFlowLoading}
/>
```

---

## 6. 关键文件清单

### 6.1 需要创建的文件（12个）

**后端（10个）**：
1. `backend/app/models/etf_share_history.py` - 数据模型
2. `backend/app/core/share_history_database.py` - 独立数据库配置
3. `backend/app/services/fund_flow_collector.py` - 采集服务
4. `backend/app/services/fund_flow_service.py` - 业务逻辑
5. `backend/app/services/fund_flow_cache_service.py` - 缓存服务
6. `backend/app/services/share_history_backup_service.py` - 备份服务
7. `backend/scripts/init_share_history_table.py` - 数据库初始化
8. `backend/tests/test_fund_flow_service.py` - 单元测试
9. `backend/tests/test_fund_flow_collector.py` - 采集器测试
10. `backend/tests/test_share_history_backup_service.py` - 备份服务测试

**前端（2个）**：
8. `frontend/components/FundFlowCard.tsx` - 卡片组件
9. `frontend/__tests__/FundFlowCard.test.tsx` - 组件测试

### 6.2 需要修改的文件（6个）

**后端（3个）**：
1. `backend/app/api/v1/endpoints/etf.py` - 新增 API 端点
2. `backend/app/api/v1/endpoints/admin.py` - 新增管理员端点
3. `backend/app/main.py` - 启动采集调度器

**前端（2个）**：
4. `frontend/lib/api.ts` - 新增类型定义
5. `frontend/app/etf/[code]/page.tsx` - 集成卡片组件

**文档（1个）**：
6. `AGENTS.md` - 更新 API 接口速查表和核心代码导航

---

## 7. 验证方案

### 7.1 数据库初始化

```bash
cd /Users/kelin/Workspace/ETFTools/backend
python scripts/init_share_history_table.py
```

验证：
```bash
# 验证独立数据库文件已创建
ls -lh etf_share_history.db

# 查看表结构
sqlite3 etf_share_history.db ".schema etf_share_history"
```

### 7.2 手动触发采集

```bash
# 获取管理员 token
TOKEN=$(curl -X POST http://localhost:8000/api/v1/auth/token \
  -d "username=admin&password=admin123" | jq -r .access_token)

# 触发采集
curl -X POST http://localhost:8000/api/v1/admin/fund-flow/collect \
  -H "Authorization: Bearer $TOKEN"
```

预期输出：
```json
{
  "success": true,
  "collected": 1485,
  "failed": 0,
  "message": "Successfully collected 1485 ETF share records"
}
```

### 7.3 测试 API 端点

```bash
# 测试获取资金流向数据
curl http://localhost:8000/api/v1/etf/510300/fund-flow | jq

# 测试强制刷新
curl "http://localhost:8000/api/v1/etf/510300/fund-flow?force_refresh=true" | jq
```

### 7.4 前端验证

1. 启动服务：`./manage.sh start`
2. 打开浏览器：`http://localhost:3000`
3. 搜索并进入 "510300" 详情页
4. 检查"资金流向"卡片显示：
   - ✅ 份额数值合理（数百亿份）
   - ✅ 规模数值合理（数千亿元）
   - ✅ 排名显示正确
   - ✅ 日期为最新交易日
   - ✅ 加载状态正常

### 7.5 单元测试

```bash
# 后端测试
cd backend
pytest tests/test_fund_flow_service.py -v
pytest tests/test_fund_flow_collector.py -v

# 前端测试
cd frontend
npx vitest run __tests__/FundFlowCard.test.tsx
```

### 7.6 定时任务验证

查看日志确认调度器启动：
```bash
tail -f backend/logs/app.log | grep "Fund flow"
```

预期输出：
```
[INFO] Fund flow collector scheduler started
[INFO] Scheduled daily collection at 16:00
[INFO] Share history backup scheduler started
[INFO] Scheduled monthly backup at 02:00 on day 1
```

### 7.7 备份功能验证

**手动导出测试**：
```bash
# 获取管理员 token
TOKEN=$(curl -X POST http://localhost:8000/api/v1/auth/token \
  -d "username=admin&password=admin123" | jq -r .access_token)

# 手动导出最近30天的数据
curl -X POST "http://localhost:8000/api/v1/admin/fund-flow/export" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2026-01-01",
    "end_date": "2026-01-31",
    "format": "csv"
  }' \
  --output share_history_export.csv
```

**验证导出文件**：
```bash
# 检查文件是否存在
ls -lh share_history_export.csv

# 查看前几行
head -n 5 share_history_export.csv
```

**验证备份目录**：
```bash
# 检查备份目录结构
ls -lh backups/share_history/
```

---

## 8. 潜在风险和缓解措施

### 风险 1：akshare 接口不稳定

**影响**：采集任务失败，无法获取最新数据

**缓解措施**：
- 降级策略：使用上一次成功的数据
- 重试机制：失败后间隔 5 分钟重试，最多 3 次
- 手动触发：提供管理员手动触发接口
- 监控告警：采集失败时记录日志

### 风险 2：数据库存储空间

**影响**：长期运行后数据量增大

**缓解措施**：
- 定期清理：保留最近 2 年数据，删除更早的记录
- 数据压缩：SQLite 自动压缩
- 监控告警：数据库文件超过 500MB 时告警

### 风险 3：份额数据更新延迟

**影响**：显示的份额数据可能不是最新的

**缓解措施**：
- 明确标注数据日期
- 在 Tooltip 中说明数据来源和更新频率
- 提供"强制刷新"功能（管理员）

### 风险 4：排名计算性能

**影响**：ETF 数量多时排名计算可能较慢

**缓解措施**：
- 使用 DiskCache 缓存排名结果（4小时过期）
- 数据库索引优化
- 异步计算（不阻塞主请求）

---

## 9. 实现顺序建议

### 第1天：后端数据层
- 创建数据模型和初始化脚本
- 实现采集服务
- 测试数据采集和存储

### 第2天：后端业务层
- 实现业务服务和缓存服务
- 新增 API 端点
- 编写单元测试

### 第3天：后端集成
- 集成定时任务
- 测试端到端流程
- 验证数据一致性

### 第4天：前端实现
- 创建卡片组件
- 集成到详情页
- 编写组件测试

### 第5天：文档更新
- 更新 AGENTS.md
- 更新 FEATURE-ROADMAP.md
- 编写使用说明

---

## 10. 未来扩展（阶段 2）

当积累至少 30 天历史数据后，可以实现：

### 10.1 份额变动趋势图

**功能**：
- 折线图展示份额变化
- 支持 1个月/3个月/1年时间维度
- 双Y轴：左侧份额，右侧净值

**技术实现**：
- 使用 recharts 库
- 复用现有图表组件样式
- 数据查询优化（索引 + 缓存）

### 10.2 净申购/赎回计算

**计算公式**：
```
净申购金额 = (今日份额 - 昨日份额) × 今日净值
```

**展示方式**：
- 正值：显示为绿色（申购）
- 负值：显示为红色（赎回）
- 附带百分比变化

### 10.3 大额事件标注

**触发条件**：
- 单日份额变动超过 5%
- 连续 3 日同向变动超过 10%

**展示方式**：
- 在趋势图上标注特殊点
- 显示具体金额和日期
- 提供事件说明（如有）

### 10.4 资金流向强度指标

**计算公式**：
```
流向强度 = 净申购金额 / 总规模 × 100%
```

**分级标准**：
- 强流入：> 5%
- 流入：1% ~ 5%
- 流出：-5% ~ -1%
- 强流出：< -5%

---

**文档创建时间**：2026-02-08
**预计实现周期**：5 个工作日
**优先级**：P1（高价值，需要一定开发投入）

