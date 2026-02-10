# ETF 自动分类 - 阶段1 实施计划

> 创建时间: 2026-02-10
> 状态: 待实施
> 前置依赖: 阶段0（已完成，分类器独立验证通过）
> 设计文档: [etf-auto-classification-design.md](../design/2026-02-10-etf-auto-classification-design.md)

---

## 1. 目标

将阶段0验证通过的分类器集成到系统中，实现：
- 后端：ETF 数据自动附带分类标签
- 前端：搜索结果中展示分类标签
- 为阶段2（标签筛选、融合搜索）打好数据基础

## 2. 关键决策

| 问题 | 决策 | 理由 |
|------|------|------|
| 融合标签搜索 | **推迟到阶段2** | 阶段1只在搜索结果中附带 tags 字段，降低复杂度；融合搜索与标签筛选器一起做更合理 |
| 首页标签展示 | **搜索页专属** | 首页卡片已有温度等摘要信息，避免信息过载 |
| API tags 格式 | **只返回 tags** | `[{label, group}]` 完整列表，前端自行截断展示，更灵活 |
| 分类器集成点 | **set_etf_list 调用前** | 只需改 2 处，比在 fetch_all_etfs 内部改 5 处更 DRY |

### 2.1 与设计文档的差异说明

设计文档阶段1原计划包含"融合标签搜索"（搜"科技"也返回标签为科技的 ETF），经讨论决定推迟到阶段2，与标签筛选器一起实现。阶段1聚焦于**数据层集成 + 基础展示**。

---

## 3. 变更范围

### 3.1 后端变更

#### 3.1.1 `backend/app/services/akshare_service.py` — 集成分类器

**改动类型**：新增 enrichment 逻辑

**具体改动**：

1. 文件顶部新增导入：
```python
from app.services.etf_classifier import ETFClassifier
```

2. 新增模块级分类器实例和辅助函数：
```python
_classifier = ETFClassifier()

def _enrich_with_tags(etf_list: List[Dict]) -> List[Dict]:
    """为 ETF 列表中的每个 ETF 添加分类标签（原地修改）"""
    for etf in etf_list:
        tags = _classifier.classify(etf.get("name", ""), etf.get("code", ""))
        etf["tags"] = [t.to_dict() for t in tags]
    return etf_list
```

3. 在 `_refresh_task()` 中，`set_etf_list(data)` 之前调用：
```python
# 现有代码（约第170行）
data = AkShareService.fetch_all_etfs()
if data:
    _enrich_with_tags(data)          # ← 新增
    etf_cache.set_etf_list(data)
```

4. 在 `get_etf_info()` 冷启动路径中，`set_etf_list()` 之前调用：
```python
# 现有代码（约第188行）
if cached_list:
    logger.info("Cold start: Restoring cache from disk.")
    _enrich_with_tags(cast(List[Dict[str, Any]], cached_list))  # ← 新增
    etf_cache.set_etf_list(cast(List[Dict[str, Any]], cached_list))
```

**设计要点**：
- `_enrich_with_tags` 原地修改 dict，不创建新列表（性能考虑）
- DiskCache 不存储 tags，tags 始终在加载到内存时实时计算
- `fetch_all_etfs()` 保持纯粹的数据获取职责，不改动
- 分类器实例为模块级单例，避免重复创建

#### 3.1.2 `backend/app/api/v1/endpoints/etf.py` — batch-price 增加 tags

**改动类型**：响应字段扩展

**具体改动**：`get_batch_price()` 函数中手动构造的 item dict 增加 tags 字段。

```python
# 现有代码（约第81-86行）
items.append({
    "code": info.get("code", code),
    "name": info.get("name", ""),
    "price": info.get("price", 0),
    "change_pct": info.get("change_pct", 0),
    "tags": info.get("tags", []),       # ← 新增
})
```

**无需修改的端点**：
- `/etf/search`：直接返回 `etf_cache.search(q)` 结果，cache 中的 dict 已包含 tags，自动透传
- `/etf/{code}/info`：返回 `info.copy()`，tags 已在 dict 中，自动包含

#### 3.1.3 `backend/app/core/cache.py` — `update_etf_info` 改为 merge 语义

**改动类型**：修复潜在 bug

**问题**：`update_etf_info()` 当前用传入的 dict **整体替换** cache 中的记录。`watchlist.py` 在两处（行 161、204）调用它时传入的是来自客户端的 dict（不含 tags），会导致对应 ETF 的 tags 丢失。

**具体改动**：将 replace 改为 merge（`existing.update(info)`），保留已有字段：

```python
# 现有代码（约第34-51行）
def update_etf_info(self, info: Dict):
    """Manually update/insert an ETF info (e.g. from client sync)"""
    code = info.get("code")
    if not code:
        return
    existing = self.etf_map.get(code)
    if existing:
        existing.update(info)          # ← 改为 merge，保留 tags 等已有字段
    else:
        self.etf_map[code] = info
    # 同步更新 list
    found = False
    for i, item in enumerate(self.etf_list):
        if item["code"] == code:
            item.update(info)          # ← 同样改为 merge
            found = True
            break
    if not found:
        self.etf_list.append(info)
```

---

### 3.2 前端变更

#### 3.2.1 `frontend/lib/api.ts` — 类型定义

**改动类型**：接口扩展

在 `ETFItem` 接口中新增可选 tags 字段：
```typescript
export interface ETFItem {
  code: string;
  name: string;
  price: number;
  change_pct: number;
  volume: number;
  // ... 现有可选字段 ...
  tags?: Array<{ label: string; group: string }>;  // ← 新增
}
```

`tags?` 为可选字段，确保向后兼容。

#### 3.2.2 `frontend/components/StockCard.tsx` — 标签展示

**改动类型**：新增 prop + 条件渲染

1. 新增 `showTags` prop：
```typescript
interface StockCardProps {
  etf: ETFItem;
  isWatched?: boolean;
  onToggleWatchlist?: (e: React.MouseEvent) => void;
  searchQuery?: string;
  showTags?: boolean;  // ← 新增，默认 false
}
```

2. 标签渲染位置：代码行（`[代码] [SH ETF]`）右侧，同一行内展示最多 2 个标签 badge。

布局示意：
```
[头像] [ETF名称]                         [价格]
       [510300] [SH ETF] [宽基] [沪深300] [+1.25%] [+]
```

3. 标签样式规范：
- 尺寸：与现有 code badge 一致（`text-[10px]`、`px-1.5 py-0.5 rounded`）
- 颜色按 group 区分：
  - `type`（大类）：蓝色系 `bg-blue-500/10 text-blue-600 dark:text-blue-400`
  - `industry`（行业）：紫色系 `bg-purple-500/10 text-purple-600 dark:text-purple-400`
  - `strategy`（策略）：琥珀色系 `bg-amber-500/10 text-amber-600 dark:text-amber-400`
  - `special`（特殊）：灰色系 `bg-secondary text-muted-foreground`
- 最多展示前 2 个标签（tags 已按 group 排序）
- 无 tags 或 `showTags=false` 时不渲染任何额外元素
- **溢出保护**：第二行 div 加 `overflow-hidden` 防止窄屏（320px）溢出，用 CSS 截断而非 JS 截断

#### 3.2.3 `frontend/app/search/page.tsx` — 传递 showTags

**改动类型**：传递 prop

```tsx
<StockCard
    key={etf.code}
    etf={etf}
    showTags={true}           // ← 新增
    isWatched={isWatched(etf.code)}
    onToggleWatchlist={(e) => toggleWatchlist(e, etf)}
/>
```

首页（`app/page.tsx`）不传 `showTags`，默认不展示标签。

---

## 4. 测试计划

> 后端用 pytest + @patch，前端用 vitest + @testing-library/react。遵循项目现有测试模式。

### 4.1 后端单元测试

#### 4.1.1 `backend/tests/services/test_enrich_with_tags.py` — 新建

测试 `_enrich_with_tags` 辅助函数的核心逻辑。

```python
import pytest
from app.services.akshare_service import _enrich_with_tags

class TestEnrichWithTags:
    def test_basic_enrichment(self):
        """ETF 列表经 enrich 后每个 dict 应包含 tags 字段"""
        etf_list = [
            {"code": "510300", "name": "沪深300ETF", "price": 3.85},
            {"code": "512480", "name": "半导体ETF", "price": 1.20},
        ]
        result = _enrich_with_tags(etf_list)

        assert result is etf_list  # 原地修改，返回同一引用
        for etf in result:
            assert "tags" in etf
            assert isinstance(etf["tags"], list)

    def test_tags_format(self):
        """tags 应为 [{"label": str, "group": str}] 格式"""
        etf_list = [{"code": "510300", "name": "沪深300ETF"}]
        _enrich_with_tags(etf_list)

        for tag in etf_list[0]["tags"]:
            assert "label" in tag
            assert "group" in tag
            assert isinstance(tag["label"], str)
            assert tag["group"] in ("type", "industry", "strategy", "special")

    def test_known_classification(self):
        """已知 ETF 应返回预期标签"""
        etf_list = [{"code": "510300", "name": "沪深300ETF"}]
        _enrich_with_tags(etf_list)
        labels = [t["label"] for t in etf_list[0]["tags"]]
        assert "宽基" in labels
        assert "沪深300" in labels

    def test_empty_name(self):
        """name 为空字符串时 tags 应为空列表"""
        etf_list = [{"code": "000000", "name": ""}]
        _enrich_with_tags(etf_list)
        assert etf_list[0]["tags"] == []

    def test_missing_name_key(self):
        """dict 中无 name 键时不报错，tags 为空列表"""
        etf_list = [{"code": "000000"}]
        _enrich_with_tags(etf_list)
        assert etf_list[0]["tags"] == []

    def test_empty_list(self):
        """空列表不报错"""
        result = _enrich_with_tags([])
        assert result == []

    def test_large_batch(self):
        """500 个 ETF 批量 enrich 应在 1 秒内完成"""
        import time
        etf_list = [{"code": f"{i:06d}", "name": f"测试ETF{i}"} for i in range(500)]
        start = time.perf_counter()
        _enrich_with_tags(etf_list)
        duration = time.perf_counter() - start
        assert duration < 1.0
```

**运行命令：** `cd backend && python -m pytest tests/services/test_enrich_with_tags.py -v`

#### 4.1.2 `backend/tests/api/test_batch_price.py` — 扩展现有测试

在现有 `TestBatchPriceEndpoint` 类中新增 tags 相关测试，沿用现有 `@patch` 模式。

```python
# 在 TestBatchPriceEndpoint 类中新增

@patch("app.api.v1.endpoints.etf.get_market_status", return_value="交易中")
@patch("app.api.v1.endpoints.etf.etf_cache")
def test_batch_price_includes_tags(self, mock_cache, mock_status):
    """batch-price 响应应包含 tags 字段"""
    mock_cache.etf_map = {
        "510300": {
            "code": "510300", "name": "沪深300ETF",
            "price": 3.85, "change_pct": 1.2,
            "tags": [{"label": "宽基", "group": "type"}, {"label": "沪深300", "group": "type"}],
        },
    }
    mock_cache.last_updated = 1700000000.0

    from app.main import app
    client = TestClient(app)
    resp = client.get("/api/v1/etf/batch-price?codes=510300")
    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert "tags" in item
    assert item["tags"][0]["label"] == "宽基"

@patch("app.api.v1.endpoints.etf.get_market_status", return_value="交易中")
@patch("app.api.v1.endpoints.etf.etf_cache")
def test_batch_price_missing_tags(self, mock_cache, mock_status):
    """ETF 无 tags 字段时应返回空列表"""
    mock_cache.etf_map = {
        "510300": {"code": "510300", "name": "沪深300ETF", "price": 3.85, "change_pct": 1.2},
    }
    mock_cache.last_updated = 1700000000.0

    from app.main import app
    client = TestClient(app)
    resp = client.get("/api/v1/etf/batch-price?codes=510300")
    item = resp.json()["items"][0]
    assert item["tags"] == []
```

**运行命令：** `cd backend && python -m pytest tests/api/test_batch_price.py -v -k tags`

#### 4.1.3 `backend/tests/core/test_cache_merge.py` — 新建

验证 `update_etf_info` 改为 merge 语义后不会丢失 tags。

```python
import pytest
from app.core.cache import ETFCacheManager

class TestUpdateEtfInfoMerge:
    def setup_method(self):
        self.cache = ETFCacheManager()
        self.cache.set_etf_list([
            {
                "code": "510300", "name": "沪深300ETF",
                "price": 3.85, "change_pct": 1.2,
                "tags": [{"label": "宽基", "group": "type"}],
            },
        ])

    def test_merge_preserves_tags(self):
        """update 不含 tags 的 dict 时，已有 tags 应保留"""
        self.cache.update_etf_info({
            "code": "510300", "price": 3.90, "change_pct": 1.5,
        })
        info = self.cache.get_etf_info("510300")
        assert info["price"] == 3.90
        assert info["tags"] == [{"label": "宽基", "group": "type"}]

    def test_merge_updates_existing_fields(self):
        """update 应正确更新已有字段"""
        self.cache.update_etf_info({"code": "510300", "name": "新名称"})
        info = self.cache.get_etf_info("510300")
        assert info["name"] == "新名称"
        assert info["tags"] == [{"label": "宽基", "group": "type"}]

    def test_merge_syncs_list_and_map(self):
        """etf_list 和 etf_map 应同步更新"""
        self.cache.update_etf_info({"code": "510300", "price": 4.00})
        map_info = self.cache.etf_map["510300"]
        list_info = next(e for e in self.cache.etf_list if e["code"] == "510300")
        assert map_info["price"] == 4.00
        assert list_info["price"] == 4.00
        assert map_info["tags"] == list_info["tags"]

    def test_insert_new_etf(self):
        """update 不存在的 ETF 应新增记录"""
        self.cache.update_etf_info({
            "code": "512480", "name": "半导体ETF", "price": 1.20,
        })
        info = self.cache.get_etf_info("512480")
        assert info is not None
        assert info["name"] == "半导体ETF"

    def test_no_code_is_noop(self):
        """无 code 字段时应静默忽略"""
        original_len = len(self.cache.etf_list)
        self.cache.update_etf_info({"name": "无代码"})
        assert len(self.cache.etf_list) == original_len
```

**运行命令：** `cd backend && python -m pytest tests/core/test_cache_merge.py -v`

### 4.2 前端单元测试

#### 4.2.1 `frontend/__tests__/StockCard.test.tsx` — 新建

沿用项目现有模式：`render` + `screen` 查询 + `vi.fn()` mock。

```tsx
import { render, screen } from "@testing-library/react"
import { describe, it, expect } from "vitest"
import { StockCard } from "@/components/StockCard"
import type { ETFItem } from "@/lib/api"

const baseETF: ETFItem = {
  code: "510300",
  name: "沪深300ETF",
  price: 3.850,
  change_pct: 1.25,
  volume: 1000000,
}

const etfWithTags: ETFItem = {
  ...baseETF,
  tags: [
    { label: "宽基", group: "type" },
    { label: "沪深300", group: "type" },
    { label: "红利", group: "strategy" },
  ],
}

describe("StockCard tags 展示", () => {
  it("showTags=true 且有 tags 时渲染标签 badge", () => {
    render(<StockCard etf={etfWithTags} showTags={true} />)
    expect(screen.getByText("宽基")).toBeInTheDocument()
    expect(screen.getByText("沪深300")).toBeInTheDocument()
  })

  it("最多展示前 2 个标签", () => {
    render(<StockCard etf={etfWithTags} showTags={true} />)
    expect(screen.getByText("宽基")).toBeInTheDocument()
    expect(screen.getByText("沪深300")).toBeInTheDocument()
    expect(screen.queryByText("红利")).not.toBeInTheDocument()
  })

  it("showTags=false 时不渲染标签", () => {
    render(<StockCard etf={etfWithTags} showTags={false} />)
    expect(screen.queryByText("宽基")).not.toBeInTheDocument()
  })

  it("showTags 默认为 false", () => {
    render(<StockCard etf={etfWithTags} />)
    expect(screen.queryByText("宽基")).not.toBeInTheDocument()
  })

  it("tags 为 undefined 时不报错", () => {
    render(<StockCard etf={baseETF} showTags={true} />)
    expect(screen.getByText("510300")).toBeInTheDocument()
  })

  it("tags 为空数组时不渲染标签区域", () => {
    const etf = { ...baseETF, tags: [] }
    render(<StockCard etf={etf} showTags={true} />)
    expect(screen.getByText("510300")).toBeInTheDocument()
  })
})
```

**运行命令：** `cd frontend && npx vitest run __tests__/StockCard.test.tsx`

### 4.3 后端集成测试

#### 4.3.1 `backend/tests/integration/test_etf_tags_integration.py` — 新建

验证从分类器 → cache → API 端点的完整数据流。

```python
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

class TestTagsIntegration:
    """验证 tags 从 enrich → cache → API 的完整链路"""

    def _setup_cache_with_tags(self):
        """辅助：用带 tags 的数据初始化 cache"""
        from app.core.cache import etf_cache
        from app.services.akshare_service import _enrich_with_tags

        etf_list = [
            {"code": "510300", "name": "沪深300ETF", "price": 3.85, "change_pct": 1.2},
            {"code": "512480", "name": "半导体ETF", "price": 1.20, "change_pct": -0.5},
            {"code": "159915", "name": "创业板ETF", "price": 2.10, "change_pct": 0.8},
        ]
        _enrich_with_tags(etf_list)
        etf_cache.set_etf_list(etf_list)
        return etf_cache

    @patch("app.api.v1.endpoints.etf.get_market_status", return_value="交易中")
    def test_search_returns_tags(self, mock_status):
        """搜索接口应透传 cache 中的 tags"""
        cache = self._setup_cache_with_tags()

        from app.main import app
        client = TestClient(app)
        resp = client.get("/api/v1/etf/search?q=半导体")
        assert resp.status_code == 200

        results = resp.json()
        semi_etf = next((r for r in results if r["code"] == "512480"), None)
        assert semi_etf is not None
        assert "tags" in semi_etf
        labels = [t["label"] for t in semi_etf["tags"]]
        assert "半导体" in labels

    @patch("app.api.v1.endpoints.etf.get_market_status", return_value="交易中")
    def test_batch_price_returns_tags(self, mock_status):
        """batch-price 接口应包含 tags"""
        self._setup_cache_with_tags()

        from app.main import app
        client = TestClient(app)
        resp = client.get("/api/v1/etf/batch-price?codes=510300,512480")
        assert resp.status_code == 200

        items = resp.json()["items"]
        assert len(items) == 2
        for item in items:
            assert "tags" in item
            assert isinstance(item["tags"], list)

    def test_update_etf_info_preserves_tags(self):
        """watchlist 同步更新价格后 tags 不丢失"""
        cache = self._setup_cache_with_tags()
        original_tags = cache.get_etf_info("510300")["tags"]

        # 模拟 watchlist 同步：只更新 price
        cache.update_etf_info({"code": "510300", "price": 4.00})

        info = cache.get_etf_info("510300")
        assert info["price"] == 4.00
        assert info["tags"] == original_tags
```

**运行命令：** `cd backend && python -m pytest tests/integration/test_etf_tags_integration.py -v`

### 4.4 端到端验证

手动验证清单，确保前后端联调正确。

#### 后端 API 验证

```bash
# 1. 启动后端
cd backend && uvicorn app.main:app --reload

# 2. 搜索接口 — 确认 tags 字段存在且内容正确
curl -s "http://localhost:8000/api/v1/etf/search?q=半导体" | python -m json.tool
# 预期：每个结果包含 "tags": [{"label": "半导体", "group": "industry"}, ...]

# 3. batch-price 接口 — 确认 tags 字段存在
curl -s "http://localhost:8000/api/v1/etf/batch-price?codes=510300,512480" | python -m json.tool
# 预期：items 中每个 item 包含 "tags" 字段

# 4. 单个 info 接口 — 确认 tags 字段存在
curl -s "http://localhost:8000/api/v1/etf/510300/info" | python -m json.tool
# 预期：返回中包含 "tags" 字段
```

#### 前端 UI 验证

```
1. 启动前端：cd frontend && npm run dev
2. 打开搜索页，搜索"半导体"
   ✓ 搜索结果卡片上应显示标签 badge（如 [半导体]）
   ✓ 标签颜色应按 group 区分（行业=紫色系）
   ✓ 最多显示 2 个标签
3. 搜索"沪深300"
   ✓ 应显示 [宽基] [沪深300] 两个蓝色系标签
4. 回到首页
   ✓ 自选列表卡片上不应显示标签
5. 在首页搜索框搜索 ETF
   ✓ 搜索结果卡片上不应显示标签（首页搜索不传 showTags）
6. 窄屏测试（Chrome DevTools → 320px 宽度）
   ✓ 标签不应导致布局溢出或换行
```

---

## 5. 实施顺序

```
Step 1: 后端 - cache.py update_etf_info 改为 merge 语义（新增）
Step 2: 后端 - akshare_service.py 集成分类器
Step 3: 后端 - etf.py batch-price 增加 tags
Step 4: 前端 - api.ts 类型定义更新
Step 5: 前端 - StockCard 增加 showTags + 标签渲染 + 溢出保护
Step 6: 前端 - search/page.tsx 传递 showTags
Step 7: 测试验证（单元测试 + 集成测试 + 端到端验证）
Step 8: 文档更新（AGENTS.md、设计文档状态）
```

- Step 1-3 可并行（后端独立改动）
- Step 4-6 可并行（前端独立改动）
- Step 7 依赖 Step 1-6 全部完成

---

## 6. 风险与注意事项

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| tags 字段向后兼容 | 旧版前端可能不识别 tags | tags 为可选字段，前端用 `?.` 访问 |
| 内存开销 | 每个 ETF 增加 tags 数据 | 约 40-80 字节/ETF，500 ETF 总计 ~40KB，可忽略 |
| 首次加载时机 | cache 未初始化时搜索无 tags | 现有行为延续，非新问题 |
| DiskCache 恢复 | 冷启动时需重新计算 tags | 已在 get_etf_info 冷启动路径中处理 |
| update_etf_info 覆盖 tags | watchlist 同步时客户端 dict 不含 tags，会丢失已有标签 | 改为 merge 语义（Step 1），已有单元测试覆盖 |
| 窄屏标签溢出 | 320px 屏幕上标签可能超出卡片宽度 | 第二行 div 加 `overflow-hidden` 溢出保护 |

---

## 7. 后续（阶段2 预告）

阶段1完成后，阶段2 将在此基础上实现：
- 融合标签搜索（搜"科技"也返回标签为科技的 ETF）
- `/etf/tags` 接口（返回所有可用标签供筛选器使用）
- `/etf/search-by-tags` 接口（按标签筛选）
- 搜索页标签筛选器 UI 组件
