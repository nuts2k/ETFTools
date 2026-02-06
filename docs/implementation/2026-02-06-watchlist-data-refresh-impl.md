# 自选列表数据刷新机制完善 — 实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 解决新增 ETF 时高级指标缺失 + 行情数据不自动刷新两个核心问题。

**Architecture:** 后端新增轻量批量价格端点 `/etf/batch-price`，前端在 WatchlistContext 的 `add()` 中实现指标异步补全，并基于 `refreshRate` 设置实现自动轮询价格更新。

**Tech Stack:** FastAPI, React 19, TypeScript, Next.js 16 (App Router)

**设计文档:** [docs/design/2026-02-06-watchlist-data-refresh-design.md](../design/2026-02-06-watchlist-data-refresh-design.md)

---

## Task 1: 后端 — 新增批量价格端点 + 测试

**Files:**
- Modify: `backend/app/api/v1/endpoints/etf.py` (在 `@router.get("/search")` 之后、`@router.get("/{code}/info")` 之前插入)
- Create: `backend/tests/api/test_batch_price.py`

### Step 1: 编写失败测试

创建 `backend/tests/api/test_batch_price.py`：

```python
"""
Tests for GET /etf/batch-price endpoint.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, PropertyMock
from fastapi.testclient import TestClient


class TestBatchPriceEndpoint:
    """Tests for /etf/batch-price endpoint."""

    def _make_etf_map(self):
        """Helper: mock etf_map data."""
        return {
            "510300": {
                "code": "510300",
                "name": "沪深300ETF",
                "price": 3.85,
                "change_pct": 0.52,
            },
            "510500": {
                "code": "510500",
                "name": "中证500ETF",
                "price": 5.12,
                "change_pct": -0.39,
            },
        }

    @patch("app.api.v1.endpoints.etf.get_market_status", return_value="交易中")
    @patch("app.api.v1.endpoints.etf.etf_cache")
    def test_batch_price_success(self, mock_cache, mock_status):
        """正常请求返回多个 ETF 价格。"""
        from app.main import app

        mock_cache.etf_map = self._make_etf_map()

        client = TestClient(app)
        response = client.get("/api/v1/etf/batch-price?codes=510300,510500")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "market_status" in data
        assert len(data["items"]) == 2
        assert data["items"][0]["code"] == "510300"
        assert data["items"][0]["price"] == 3.85
        assert data["market_status"] == "交易中"

    @patch("app.api.v1.endpoints.etf.get_market_status", return_value="已收盘")
    @patch("app.api.v1.endpoints.etf.etf_cache")
    def test_batch_price_market_closed(self, mock_cache, mock_status):
        """已收盘时 market_status 正确返回。"""
        from app.main import app

        mock_cache.etf_map = self._make_etf_map()

        client = TestClient(app)
        response = client.get("/api/v1/etf/batch-price?codes=510300")

        assert response.status_code == 200
        data = response.json()
        assert data["market_status"] == "已收盘"

    @patch("app.api.v1.endpoints.etf.etf_cache")
    def test_batch_price_unknown_code_skipped(self, mock_cache):
        """未知代码被静默跳过，不报错。"""
        from app.main import app

        mock_cache.etf_map = self._make_etf_map()

        client = TestClient(app)
        response = client.get("/api/v1/etf/batch-price?codes=999999")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 0

    def test_batch_price_empty_codes(self):
        """空 codes 参数返回 400。"""
        from app.main import app

        client = TestClient(app)
        response = client.get("/api/v1/etf/batch-price?codes=")

        assert response.status_code == 400

    def test_batch_price_too_many_codes(self):
        """超过 50 个代码返回 400。"""
        from app.main import app

        codes = ",".join([str(i) for i in range(51)])
        client = TestClient(app)
        response = client.get(f"/api/v1/etf/batch-price?codes={codes}")

        assert response.status_code == 400
```

### Step 2: 运行测试，确认失败

```bash
cd backend && python -m pytest tests/api/test_batch_price.py -v
```

预期：FAIL — 404 (路由不存在)

### Step 3: 实现端点

修改 `backend/app/api/v1/endpoints/etf.py`，在 `@router.get("/search")` 函数之后、`@router.get("/{code}/info")` 之前插入：

```python
@router.get("/batch-price")
async def get_batch_price(
    codes: str = Query(..., description="逗号分隔的 ETF 代码列表，如 510300,510500")
):
    """
    批量获取 ETF 实时价格（轻量级，仅从内存缓存读取）
    """
    code_list = [c.strip() for c in codes.split(",") if c.strip()]
    if not code_list or len(code_list) > 50:
        raise HTTPException(status_code=400, detail="codes 参数无效或超过 50 个")

    items = []
    for code in code_list:
        info = etf_cache.etf_map.get(code)
        if info:
            items.append({
                "code": info.get("code", code),
                "name": info.get("name", ""),
                "price": info.get("price", 0),
                "change_pct": info.get("change_pct", 0),
            })

    return {
        "items": items,
        "market_status": get_market_status(),
    }
```

**关键：** 必须放在 `/{code}/info` 之前，否则 FastAPI 会将 `batch-price` 匹配为 `{code}` 路径参数。

### Step 4: 运行测试，确认通过

```bash
cd backend && python -m pytest tests/api/test_batch_price.py -v
```

预期：5 tests PASSED

### Step 5: 运行全量后端测试，确认无回归

```bash
cd backend && python -m pytest tests/ -v
```

预期：全部 PASSED

### Step 6: 提交

```bash
git add backend/app/api/v1/endpoints/etf.py backend/tests/api/test_batch_price.py
git commit -m "feat(api): add GET /etf/batch-price endpoint for lightweight batch price queries"
```

---

## Task 2: 前端 — add() 后自动补全指标

**Files:**
- Modify: `frontend/lib/watchlist-context.tsx`

### Step 1: 添加 `fetchMetricsForItem` 辅助函数

在 `WatchlistProvider` 函数体内、`add` 函数之前，添加辅助函数：

```typescript
const fetchMetricsForItem = async (code: string): Promise<Partial<ETFItem> | null> => {
  try {
    const [infoResult, metricsResult] = await Promise.allSettled([
      fetchClient<ETFDetail>(`/etf/${code}/info`),
      fetchClient<ETFMetrics>(`/etf/${code}/metrics?period=5y`),
    ]);
    const info = infoResult.status === "fulfilled" ? infoResult.value : null;
    const metrics = metricsResult.status === "fulfilled" ? metricsResult.value : null;
    return {
      ...(info && { price: info.price, change_pct: info.change_pct }),
      ...(metrics && {
        atr: metrics.atr,
        current_drawdown: metrics.current_drawdown,
        weekly_direction: metrics.weekly_trend?.direction,
        consecutive_weeks: metrics.weekly_trend?.consecutive_weeks,
        temperature_score: metrics.temperature?.score,
        temperature_level: metrics.temperature?.level,
      }),
    };
  } catch {
    return null;
  }
};
```

**位置：** `frontend/lib/watchlist-context.tsx` 的 `WatchlistProvider` 内部，在现有 `const add = async (item: ETFItem) => {` 之前（约第 104 行前）。

### Step 2: 修改 `add()` 函数 — 云端模式补全

在 `add()` 函数的云端分支（`if (user && token)` 块）末尾，POST 成功后重新获取完整列表：

将现有代码（`frontend/lib/watchlist-context.tsx:112-125`）：

```typescript
    if (user && token) {
      try {
        await fetch(`${API_BASE_URL}/watchlist/${item.code}`, {
          method: "POST",
          headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`
          },
          body: JSON.stringify(item)
        });
      } catch (e) {
        // Revert on error? For MVP we just log
        console.error("Cloud add failed", e);
      }
    }
```

替换为：

```typescript
    if (user && token) {
      try {
        await fetch(`${API_BASE_URL}/watchlist/${item.code}`, {
          method: "POST",
          headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`
          },
          body: JSON.stringify(item)
        });
        // POST 成功后，重新获取完整列表（含指标）
        const res = await fetch(`${API_BASE_URL}/watchlist/`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (res.ok) {
          const data = await res.json();
          setWatchlist(data);
        }
      } catch (e) {
        console.error("Cloud add failed", e);
      }
    }
```

### Step 3: 修改 `add()` 函数 — 本地模式补全

在 `add()` 函数的 `else` 分支（本地模式）末尾，`localStorage.setItem` 之后添加异步补全。

将现有代码（`frontend/lib/watchlist-context.tsx:126-128`）：

```typescript
    } else {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(newList));
    }
```

替换为：

```typescript
    } else {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(newList));
      // 异步补全指标（不阻塞 add 操作）
      fetchMetricsForItem(item.code).then((enriched) => {
        if (enriched) {
          setWatchlist(prev => {
            const updated = prev.map(i => i.code === item.code ? { ...i, ...enriched } : i);
            localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
            return updated;
          });
        }
      });
    }
```

### Step 4: 类型检查

```bash
cd frontend && npx tsc --noEmit
```

预期：无错误

### Step 5: 提交

```bash
git add frontend/lib/watchlist-context.tsx
git commit -m "feat(watchlist): auto-enrich metrics after adding ETF to watchlist"
```

---

## Task 3: 前端 — 自动轮询价格

**Files:**
- Modify: `frontend/lib/watchlist-context.tsx`

**前置确认：** `layout.tsx` 中 Provider 嵌套顺序为 `AuthProvider > SettingsProvider > WatchlistProvider`，因此 WatchlistProvider 内部可以安全调用 `useSettings()`。

### Step 1: 添加 `useSettings` 导入和 `isTradingHours` 辅助函数

在 `frontend/lib/watchlist-context.tsx` 文件顶部添加导入：

```typescript
import { useSettings } from "@/hooks/use-settings";
```

在 `WatchlistProvider` 函数体内顶部（现有 state 声明之后）添加：

```typescript
const { settings } = useSettings();
const { refreshRate } = settings;
```

在 `WatchlistProvider` 函数体内（`fetchMetricsForItem` 之前）添加辅助函数：

```typescript
function isTradingHours(): boolean {
  const now = new Date();
  const day = now.getDay();
  if (day === 0 || day === 6) return false; // 周末

  const minutes = now.getHours() * 60 + now.getMinutes();
  // 9:15-11:30 或 13:00-15:00
  return (minutes >= 555 && minutes <= 690) || (minutes >= 780 && minutes <= 900);
}
```

### Step 2: 添加轮询 useEffect

在 `WatchlistProvider` 内部，现有 `return (` 之前，添加轮询 effect：

```typescript
// 自动轮询价格
useEffect(() => {
  if (refreshRate === 0 || watchlist.length === 0 || !isLoaded) return;

  const poll = async () => {
    if (document.hidden || !isTradingHours()) return;

    const codes = watchlist.map(i => i.code).join(",");
    try {
      const res = await fetch(`${API_BASE_URL}/etf/batch-price?codes=${codes}`);
      if (!res.ok) return;
      const data = await res.json();

      // 如果已收盘，不再更新
      if (data.market_status !== "交易中") return;

      const priceMap = new Map(
        data.items.map((item: any) => [item.code, item])
      );

      setWatchlist(prev =>
        prev.map(item => {
          const updated = priceMap.get(item.code);
          if (!updated) return item;
          return { ...item, price: updated.price, change_pct: updated.change_pct };
        })
      );
    } catch (e) {
      console.error("Price poll failed", e);
    }
  };

  const intervalId = setInterval(poll, refreshRate * 1000);

  // 页面可见性变化时也触发一次
  const handleVisibility = () => {
    if (!document.hidden) poll();
  };
  document.addEventListener("visibilitychange", handleVisibility);

  return () => {
    clearInterval(intervalId);
    document.removeEventListener("visibilitychange", handleVisibility);
  };
}, [refreshRate, watchlist.length, isLoaded]);
```

### Step 3: 类型检查

```bash
cd frontend && npx tsc --noEmit
```

预期：无错误

### Step 4: 提交

```bash
git add frontend/lib/watchlist-context.tsx
git commit -m "feat(watchlist): add auto-polling for real-time price updates during trading hours"
```

---

## Task 4: 前端 — 调整刷新频率选项

**Files:**
- Modify: `frontend/lib/settings-context.tsx`
- Modify: `frontend/app/settings/page.tsx`

### Step 1: 修改 RefreshRate 类型和默认值

在 `frontend/lib/settings-context.tsx:8` 将：

```typescript
export type RefreshRate = 5 | 10 | 30 | 0; // 0 = Manual
```

替换为：

```typescript
export type RefreshRate = 15 | 30 | 60 | 0; // 0 = Manual
```

在 `frontend/lib/settings-context.tsx:19` 将：

```typescript
  refreshRate: 5,
```

替换为：

```typescript
  refreshRate: 30,
```

### Step 2: 更新设置页面选项

在 `frontend/app/settings/page.tsx:123-128` 将：

```tsx
<option value={5}>每 5 秒</option>
<option value={10}>每 10 秒</option>
<option value={30}>每 30 秒</option>
<option value={0}>手动</option>
```

替换为：

```tsx
<option value={15}>每 15 秒</option>
<option value={30}>每 30 秒</option>
<option value={60}>每 60 秒</option>
<option value={0}>手动</option>
```

### Step 3: 显示文本确认

同文件 `frontend/app/settings/page.tsx:129-131` 的显示文本：

```tsx
{settings.refreshRate === 0 ? "手动" : `${settings.refreshRate}秒`}
```

无需修改，此处已是动态显示，会自动适配新的数值。

### Step 4: 类型检查

```bash
cd frontend && npx tsc --noEmit
```

预期：无错误

### Step 5: 提交

```bash
git add frontend/lib/settings-context.tsx frontend/app/settings/page.tsx
git commit -m "feat(settings): update refresh rate options to 15/30/60s with 30s default"
```

---

## Task 5: 文档更新

**Files:**
- Modify: `AGENTS.md`

### Step 1: 更新 API 接口速查表

在 `AGENTS.md` 第 6 节 API 接口速查表中，`/etf/{code}/metrics` 行（第 189 行）之后添加一行：

```markdown
| `/etf/batch-price?codes={codes}` | GET | 批量获取实时价格（轻量级，含交易状态） |
```

### Step 2: 提交

```bash
git add AGENTS.md
git commit -m "docs: add batch-price endpoint to API reference in AGENTS.md"
```

---

## 最终验证清单

### 自动化验证

```bash
# 后端全量测试
cd backend && python -m pytest tests/ -v

# 前端类型检查
cd frontend && npx tsc --noEmit
```

### 手动验证

| # | 场景 | 预期结果 |
|---|------|---------|
| 1 | 登录后添加新 ETF | 卡片几秒内显示完整指标（ATR、回撤、趋势、温度） |
| 2 | 退出登录，本地模式添加新 ETF | 同样补全指标 |
| 3 | 交易时段观察价格 | 按设定间隔自动更新 |
| 4 | 非交易时段 | 不轮询（控制台无请求） |
| 5 | 设置页修改刷新频率 | 立即生效，轮询间隔变化 |
| 6 | 设置刷新频率为"手动" | 停止轮询 |
| 7 | 切换到其他标签页再切回 | 切回时立即触发一次价格更新 |
| 8 | 下拉刷新 | 仍正常工作，不受轮询影响 |

---

## 修改文件总览

| 操作 | 文件 | Task |
|------|------|------|
| **新增** | `backend/tests/api/test_batch_price.py` | Task 1 |
| **修改** | `backend/app/api/v1/endpoints/etf.py` | Task 1 |
| **修改** | `frontend/lib/watchlist-context.tsx` | Task 2, 3 |
| **修改** | `frontend/lib/settings-context.tsx` | Task 4 |
| **修改** | `frontend/app/settings/page.tsx` | Task 4 |
| **修改** | `AGENTS.md` | Task 5 |

---

*最后更新: 2026-02-06*