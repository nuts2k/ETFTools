# 自选列表数据刷新机制完善 — 设计文档

**Goal:** 解决两个核心问题：(1) 新增 ETF 时高级指标缺失；(2) 行情数据不自动刷新。

**Architecture:** 后端新增轻量批量价格端点，前端在 WatchlistContext 中实现 add() 后指标补全 + 基于 refreshRate 的自动轮询。

**Tech Stack:** FastAPI, React 19, TypeScript, Next.js 16 (App Router)

---

## 问题分析

### 问题 1：新增 ETF 指标缺失

搜索结果只包含 5 个基础字段（code, name, price, change_pct, volume），添加到自选后高级指标（ATR、回撤、趋势、温度）不显示，需要手动下拉刷新才能补全。

### 问题 2：数据不自动刷新

`refreshRate` 设置已存在（settings-context.tsx）但从未被消费，价格在页面停留期间不会更新。用户必须手动下拉刷新才能看到最新价格。

---

## 修改文件清单

| 操作 | 文件 | 说明 |
|------|------|------|
| **修改** | `backend/app/api/v1/endpoints/etf.py` | 新增 `GET /etf/batch-price` 批量价格端点 |
| **修改** | `frontend/lib/watchlist-context.tsx` | add() 后自动补全指标 + 自动轮询逻辑 |
| **修改** | `frontend/lib/settings-context.tsx` | RefreshRate 类型改为 15/30/60/0 |
| **修改** | `frontend/app/settings/page.tsx` | 更新刷新频率选项 UI |
| **修改** | `AGENTS.md` | 更新 API 接口速查表 |

---

## Task 1: 后端 — 新增批量价格端点

**Files:**
- Modify: `backend/app/api/v1/endpoints/etf.py`

### 端点设计

```
GET /etf/batch-price?codes=510300,510500,510880
```

**特点：**
- 从 `etf_cache.etf_map` 批量读取（O(1) 每个）
- 只返回价格相关字段，不计算任何指标，极轻量
- 附带 `market_status` 字段，前端据此决定是否继续轮询
- 最多 50 个代码，防止滥用

### 响应格式

```json
{
  "items": [
    {"code": "510300", "name": "沪深300ETF", "price": 3.85, "change_pct": 0.52},
    {"code": "510500", "name": "中证500ETF", "price": 5.12, "change_pct": -0.39}
  ],
  "market_status": "交易中"
}
```

### 实现位置

在 `@router.get("/search")` 之后、`@router.get("/{code}/info")` 之前插入新端点。

**注意：** 必须放在 `/{code}/info` 之前，否则 FastAPI 路由匹配会将 `batch-price` 当作 `{code}` 参数。

### 实现代码

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

### 验证

```bash
cd backend && python -m pytest tests/ -v
```

---

## Task 2: 前端 — add() 后自动补全指标

**Files:**
- Modify: `frontend/lib/watchlist-context.tsx`

### 设计思路

在 `add()` 函数中，乐观更新（立即显示基础字段）后，异步补全高级指标：

- **云端模式**：POST 成功后调用 `GET /watchlist/` 获取完整数据（后端已计算所有指标）
- **本地模式**：对新 item 调用 `/etf/{code}/info` + `/etf/{code}/metrics?period=5y` 补全

### 补全字段

| 字段 | 来源 |
|------|------|
| `price`, `change_pct` | `/etf/{code}/info` |
| `atr` | `/etf/{code}/metrics` → `atr` |
| `current_drawdown` | `/etf/{code}/metrics` → `current_drawdown` |
| `weekly_direction` | `/etf/{code}/metrics` → `weekly_trend.direction` |
| `consecutive_weeks` | `/etf/{code}/metrics` → `weekly_trend.consecutive_weeks` |
| `temperature_score` | `/etf/{code}/metrics` → `temperature.score` |
| `temperature_level` | `/etf/{code}/metrics` → `temperature.level` |

### 实现方式

在现有 `add()` 函数的 cloud/local 分支末尾，各添加一个异步补全调用：

**云端模式补全：**

```typescript
// POST 成功后，重新获取完整列表（含指标）
try {
  const res = await fetch(`${API_BASE_URL}/watchlist/`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (res.ok) {
    const data = await res.json();
    setWatchlist(data);
  }
} catch {}
```

**本地模式补全：**

```typescript
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
```

**辅助函数 `fetchMetricsForItem`：**

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

### 验证

```bash
cd frontend && npx tsc --noEmit
```

---

## Task 3: 前端 — 自动轮询价格

**Files:**
- Modify: `frontend/lib/watchlist-context.tsx`

### 设计思路

在 WatchlistProvider 中添加 `useEffect` 轮询，消费 `refreshRate` 设置。

### 轮询规则

| 条件 | 行为 |
|------|------|
| `refreshRate === 0` | 不轮询（手动模式） |
| 非交易时段 | 不轮询 |
| `document.hidden === true` | 暂停轮询 |
| 自选列表为空 | 不轮询 |
| 交易时段 + 页面可见 | 按 `refreshRate` 秒间隔调用 `/etf/batch-price` |

### 交易时段判断（前端）

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

### 轮询 useEffect

```typescript
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

### 注意事项

- `useSettings()` 不能在 WatchlistProvider 内直接调用（可能存在 Context 嵌套顺序问题），需要通过 props 或确认 Provider 嵌套顺序
- 需要检查 `layout.tsx` 中 `SettingsProvider` 是否包裹在 `WatchlistProvider` 外层

### 验证

```bash
cd frontend && npx tsc --noEmit
```

---

## Task 4: 前端 — 调整刷新频率选项

**Files:**
- Modify: `frontend/lib/settings-context.tsx`
- Modify: `frontend/app/settings/page.tsx`

### settings-context.tsx 变更

**RefreshRate 类型：**

```typescript
// 旧：export type RefreshRate = 5 | 10 | 30 | 0;
// 新：
export type RefreshRate = 15 | 30 | 60 | 0; // 0 = Manual
```

**默认值：**

```typescript
// 旧：refreshRate: 5,
// 新：
refreshRate: 30,
```

### settings/page.tsx 变更

更新 select 选项：

```tsx
{/* 旧选项 */}
<option value={5}>每 5 秒</option>
<option value={10}>每 10 秒</option>
<option value={30}>每 30 秒</option>
<option value={0}>手动</option>

{/* 新选项 */}
<option value={15}>每 15 秒</option>
<option value={30}>每 30 秒</option>
<option value={60}>每 60 秒</option>
<option value={0}>手动</option>
```

### 验证

```bash
cd frontend && npx tsc --noEmit
```

---

## Task 5: 文档更新

**Files:**
- Modify: `AGENTS.md`

### 变更内容

在 AGENTS.md 第 6 节 API 接口速查表中，`/etf/{code}/metrics` 行之后添加：

```markdown
| `/etf/batch-price?codes={codes}` | GET | 批量获取实时价格（轻量级，含交易状态） |
```

---

## 验证方式

1. `cd backend && python -m pytest tests/ -v` — 后端测试通过
2. `cd frontend && npx tsc --noEmit` — 前端类型检查通过
3. 启动前后端，登录后添加新 ETF → 卡片几秒内显示完整指标
4. 退出登录，本地模式添加新 ETF → 同样补全指标
5. 交易时段观察价格是否按设定间隔自动更新
6. 非交易时段确认不轮询
7. 设置页修改刷新频率，确认立即生效
8. 下拉刷新仍正常工作

---

## 回滚方案

```bash
git revert HEAD
```

---

*最后更新: 2026-02-06*
