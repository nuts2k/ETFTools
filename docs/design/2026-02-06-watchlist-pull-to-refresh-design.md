# Watchlist 下拉刷新设计文档

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为自选列表页面添加下拉刷新功能，支持刷新行情价格和所有指标数据（温度、趋势、ATR、回撤），提供原生 App 级别的交互体验。

**Architecture:** 自定义 `usePullToRefresh` Hook 处理触摸手势状态机，`PullToRefreshIndicator` 组件提供视觉反馈，`WatchlistContext` 新增 `refresh()` 方法支持 Cloud/Local 双模式数据刷新。

**Tech Stack:** React 19, TypeScript, Tailwind CSS, Next.js 16 (App Router)

---

## 设计规范

### 交互流程

```
用户在列表顶部下拉
  → 出现下拉指示器（箭头 + "下拉刷新"）
  → 超过阈值（80px）后文字变为"释放刷新" + haptic 反馈
  → 释放手指
  → 指示器显示旋转动画 + "正在刷新..."
  → 数据更新完成
  → 指示器显示"刷新完成" → 400ms 后收起
  → 状态栏时间戳更新
```

### 手势状态机

```
idle → pulling → threshold → refreshing → complete → idle
                    ↓ (释放未达阈值)
                   idle
```

| 状态 | 触发条件 | 视觉表现 |
|------|---------|---------|
| `idle` | 初始/完成后 | 隐藏 |
| `pulling` | scrollTop=0 且向下拉动 | 箭头按进度旋转 + "下拉刷新" |
| `threshold` | pullDistance ≥ 80px | 箭头旋转 180° + "释放刷新"（text-primary） |
| `refreshing` | 释放且已达阈值 | RefreshCw animate-spin + "正在刷新..." |
| `complete` | onRefresh 完成 | Check 图标 + "刷新完成"，400ms 后淡出 |

### 手势冲突避免策略

| 手势 | 事件目标 | 激活条件 | 冲突风险 |
|------|---------|---------|---------|
| **下拉刷新** | 滚动容器 | scrollTop=0 + 向下拉 | - |
| **拖拽排序** (@dnd-kit) | 单个 item | 250ms 长按 + 编辑模式 | 无（编辑模式下禁用刷新） |
| **长按进入编辑** | 单个 item | 500ms 长按 | 无（不同事件目标） |
| **正常滚动** | 滚动容器 | scrollTop > 0 | 无（scrollTop 守卫） |

### 阻力曲线

```
displayDistance = delta × (1 - delta / (maxPull × 3))
```

拉动越远阻力越大，最大视觉位移 120px，提供自然的橡皮筋手感。

### 禁用条件

- `isSearchMode === true`（搜索模式覆盖列表）
- `isEditing === true`（编辑模式需要拖拽排序）

---

## 数据刷新策略

### Cloud 模式（已登录）

单次 API 调用 `GET /api/v1/watchlist/`，后端 ThreadPoolExecutor 并行处理，返回所有字段：
- `price`, `change_pct`（实时行情）
- `atr`, `current_drawdown`（风险指标）
- `weekly_direction`, `consecutive_weeks`（周趋势）
- `temperature_score`, `temperature_level`（市场温度）

### Local 模式（未登录）

对每个 item 并行调用公开 API：
- `GET /etf/{code}/info` → price, change_pct
- `GET /etf/{code}/metrics?period=5y` → atr, current_drawdown, weekly_trend.direction, weekly_trend.consecutive_weeks, temperature.score, temperature.level

使用 `Promise.allSettled` 确保单个失败不阻塞，失败项保留旧数据。更新后同步写入 localStorage。

### 保护机制

- **冷却时间**: 3 秒内不重复触发
- **超时保护**: 15 秒 `Promise.race` 超时
- **错误容忍**: 网络失败时保留旧数据，不崩溃

---

## 文件变更清单

| 操作 | 文件 | 说明 |
|------|------|------|
| **新建** | `frontend/hooks/use-pull-to-refresh.ts` | 下拉刷新手势 Hook |
| **新建** | `frontend/components/PullToRefreshIndicator.tsx` | 下拉视觉反馈组件 |
| **修改** | `frontend/lib/watchlist-context.tsx` | 添加 `refresh()` 方法 |
| **修改** | `frontend/app/page.tsx` | 集成 Hook、指示器、滚动容器改造 |

---

## Task 1: WatchlistContext 添加 `refresh()` 方法

**Files:**
- Modify: `frontend/lib/watchlist-context.tsx`

**Step 1: 扩展 Context 接口**

在 `WatchlistContextType` 接口中添加 `refresh` 方法：

```typescript
interface WatchlistContextType {
  watchlist: ETFItem[];
  add: (item: ETFItem) => Promise<void>;
  remove: (code: string) => Promise<void>;
  reorder: (newOrderCodes: string[]) => Promise<void>;
  isWatched: (code: string) => boolean;
  isLoaded: boolean;
  refresh: () => Promise<void>;  // 新增
}
```

**Step 2: 添加导入**

在文件顶部添加 `fetchClient` 导入：

```typescript
import { type ETFItem, API_BASE_URL, fetchClient } from "@/lib/api";
```

同时导入需要的类型（用于 local 模式 metrics 响应解析）：

```typescript
import type { ETFDetail, ETFMetrics } from "@/lib/api";
```

**Step 3: 实现 Cloud 模式刷新**

在 `WatchlistProvider` 组件内、`isWatched` 函数之后添加 `refresh` 函数：

```typescript
const refresh = async () => {
  if (user && token) {
    // Cloud 模式：单次 API 调用
    try {
      const res = await fetch(`${API_BASE_URL}/watchlist/`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setWatchlist(data);
      }
    } catch (e) {
      console.error("Refresh failed", e);
    }
  } else {
    // Local 模式：并行调用各 ETF 的公开 API
    await refreshLocal();
  }
};
```

**Step 4: 实现 Local 模式刷新**

在 `refresh` 函数之后添加 `refreshLocal`：

```typescript
const refreshLocal = async () => {
  const currentList = [...watchlist];
  if (currentList.length === 0) return;

  const results = await Promise.allSettled(
    currentList.map(async (item) => {
      const [info, metrics] = await Promise.all([
        fetchClient<ETFDetail>(`/etf/${item.code}/info`),
        fetchClient<ETFMetrics>(`/etf/${item.code}/metrics?period=5y`),
      ]);
      return {
        ...item,
        price: info.price ?? item.price,
        change_pct: info.change_pct ?? item.change_pct,
        atr: metrics.atr ?? item.atr,
        current_drawdown: metrics.current_drawdown ?? item.current_drawdown,
        weekly_direction: metrics.weekly_trend?.direction ?? item.weekly_direction,
        consecutive_weeks: metrics.weekly_trend?.consecutive_weeks ?? item.consecutive_weeks,
        temperature_score: metrics.temperature?.score ?? item.temperature_score,
        temperature_level: metrics.temperature?.level ?? item.temperature_level,
      };
    })
  );

  const newList = results.map((result, i) =>
    result.status === "fulfilled" ? result.value : currentList[i]
  );
  setWatchlist(newList);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(newList));
};
```

**Step 5: 更新 Provider value**

将 `refresh` 添加到 Provider 的 value 中：

```typescript
<WatchlistContext.Provider value={{ watchlist, add, remove, reorder, isWatched, isLoaded, refresh }}>
```

**Step 6: 验证类型正确**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无错误输出

---

## Task 2: 创建 `usePullToRefresh` Hook

**Files:**
- Create: `frontend/hooks/use-pull-to-refresh.ts`

**Step 1: Hook 接口定义**

```typescript
import { useState, useRef, useEffect, useCallback } from "react";

type PullState = "idle" | "pulling" | "threshold" | "refreshing" | "complete";

interface UsePullToRefreshOptions {
  onRefresh: () => Promise<void>;
  scrollRef: React.RefObject<HTMLElement | null>;
  threshold?: number;    // 默认 80
  maxPull?: number;      // 默认 120
  cooldown?: number;     // 默认 3000ms
  disabled?: boolean;
}

interface UsePullToRefreshReturn {
  pullDistance: number;
  state: PullState;
}
```

**Step 2: 核心状态和 Refs**

```typescript
export function usePullToRefresh({
  onRefresh,
  scrollRef,
  threshold = 80,
  maxPull = 120,
  cooldown = 3000,
  disabled = false,
}: UsePullToRefreshOptions): UsePullToRefreshReturn {
  const [pullDistance, setPullDistance] = useState(0);
  const [state, setState] = useState<PullState>("idle");

  const startY = useRef(0);
  const startX = useRef(0);
  const isTracking = useRef(false);
  const lastRefreshTime = useRef(0);
  const directionLocked = useRef<"vertical" | "horizontal" | null>(null);
  const currentState = useRef<PullState>("idle");
```

**Step 3: 阻力曲线函数**

```typescript
  const applyResistance = useCallback(
    (delta: number) => {
      // 橡皮筋效果：拉动越远阻力越大
      const resistance = 1 - delta / (maxPull * 3);
      return Math.min(delta * Math.max(resistance, 0.2), maxPull);
    },
    [maxPull]
  );
```

**Step 4: Touch 事件处理器**

`onTouchStart`:
- 检查 `disabled`、冷却时间、`scrollTop <= 0`
- 记录起始坐标，设置 `isTracking = true`

`onTouchMove`:
- 方向锁定：移动 10px 后判断水平/垂直，水平则放弃
- 计算 deltaY，应用阻力曲线得到 displayDistance
- 更新 `pullDistance` 和 `state`（pulling/threshold）
- 跨越阈值时触发 haptic 反馈 `navigator.vibrate(10)`
- 调用 `e.preventDefault()` 阻止浏览器原生下拉

`onTouchEnd`:
- 如果 state 为 threshold → 进入 refreshing，执行 `onRefresh()`
- 如果 state 为 pulling → 回到 idle
- refreshing 完成后 → complete → 400ms 延迟 → idle

**Step 5: useEffect 挂载原生事件监听器**

使用 `useEffect` 将 touchstart/touchmove/touchend 挂载到 `scrollRef.current`：
- touchmove 使用 `{ passive: false }` 以支持 `preventDefault()`
- cleanup 函数移除所有监听器

**Step 6: 超时保护**

在 refreshing 阶段使用 `Promise.race`：

```typescript
const timeoutPromise = new Promise<void>((_, reject) =>
  setTimeout(() => reject(new Error("Refresh timeout")), 15000)
);
try {
  await Promise.race([onRefresh(), timeoutPromise]);
} catch {
  // 超时或失败，静默处理
}
```

**Step 7: 返回值**

```typescript
  return { pullDistance, state };
}
```

**Step 8: 验证**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无错误输出

---

## Task 3: 创建 `PullToRefreshIndicator` 组件

**Files:**
- Create: `frontend/components/PullToRefreshIndicator.tsx`

**Step 1: 组件接口**

```typescript
"use client";

import { RefreshCw, Check } from "lucide-react";
import { cn } from "@/lib/utils";

type PullState = "idle" | "pulling" | "threshold" | "refreshing" | "complete";

interface PullToRefreshIndicatorProps {
  pullDistance: number;
  state: PullState;
  threshold: number;
}
```

**Step 2: 组件实现**

- 外层 div: `overflow-hidden`，高度 = `pullDistance`（idle 时为 0）
- 拉动中禁用 CSS transition（避免延迟），释放后启用 `transition-all duration-300`
- 内容居中：`flex items-center justify-center gap-2`

**Step 3: 各状态视觉映射**

| 状态 | 图标 | 文字 | 样式 |
|------|------|------|------|
| pulling | `RefreshCw` 按进度旋转（`rotate(progress * 180deg)`） | "下拉刷新" | `text-muted-foreground` |
| threshold | `RefreshCw` 旋转 180° | "释放刷新" | `text-primary` |
| refreshing | `RefreshCw` + `animate-spin` | "正在刷新..." | `text-primary` |
| complete | `Check` 图标 | "刷新完成" | `text-primary` |

图标尺寸: `h-4 w-4`，文字: `text-xs`

**Step 4: 验证**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无错误输出

---

## Task 4: 集成到 `page.tsx`

**Files:**
- Modify: `frontend/app/page.tsx`

**Step 1: 添加导入**

```typescript
import { useRef } from "react";
import { usePullToRefresh } from "@/hooks/use-pull-to-refresh";
import { PullToRefreshIndicator } from "@/components/PullToRefreshIndicator";
```

注意：`useRef` 需要添加到现有的 `import { useState, useEffect } from "react"` 中。

**Step 2: 从 useWatchlist 解构 refresh**

```typescript
const { watchlist, isLoaded, add, remove, reorder, isWatched, refresh } = useWatchlist();
```

**Step 3: 添加 scrollRef 和 Hook 调用**

在组件内、现有 state 声明之后添加：

```typescript
const scrollRef = useRef<HTMLDivElement>(null);

const { pullDistance, state: pullState } = usePullToRefresh({
  scrollRef,
  onRefresh: async () => {
    await refresh();
    setLastUpdated(new Date());
  },
  disabled: isSearchMode || isEditing,
});
```

**Step 4: 改造滚动容器**

将最外层 div 从：

```html
<div className="flex flex-col min-h-[100dvh] bg-background pb-20">
```

改为：

```html
<div ref={scrollRef} className="flex flex-col h-[100dvh] bg-background pb-20 overflow-y-auto overscroll-y-contain">
```

关键变更：
- 添加 `ref={scrollRef}`
- `min-h-[100dvh]` → `h-[100dvh]`（固定高度，成为滚动容器）
- 添加 `overflow-y-auto`（启用内部滚动）
- 添加 `overscroll-y-contain`（阻止浏览器原生下拉刷新）

**Step 5: 插入 PullToRefreshIndicator**

在 `{!isSearchMode && (` 块内，status bar 之前插入指示器：

```tsx
{!isSearchMode && (
  <>
    {/* 下拉刷新指示器 */}
    <PullToRefreshIndicator
      pullDistance={pullDistance}
      state={pullState}
      threshold={80}
    />

    {/* Status Bar（原有代码不变） */}
    <div className="flex items-center justify-between px-6 py-2">
      ...
    </div>
    ...
  </>
)}
```

**Step 6: 验证编译**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无错误输出

---

## Task 5: 端到端验证

**Step 1: 启动服务**

Run: `./manage.sh start`
Expected: 前后端正常启动

**Step 2: 功能验证清单**

在浏览器 http://localhost:3000 中逐项检查：

| 场景 | 操作 | 预期结果 |
|------|------|---------|
| 基本下拉刷新 | 列表顶部向下拉动超过阈值后释放 | 出现指示器动画，数据刷新，时间戳更新 |
| 未达阈值释放 | 下拉不到 80px 后释放 | 指示器回弹，不触发刷新 |
| 编辑模式禁用 | 进入编辑模式后下拉 | 不触发下拉刷新 |
| 搜索模式禁用 | 进入搜索模式后下拉 | 不触发下拉刷新 |
| 冷却机制 | 刷新完成后 3 秒内再次下拉 | 不触发刷新 |
| 列表中间下拉 | 滚动到中间位置后下拉 | 正常滚动，不触发刷新 |
| 长按进入编辑 | 长按某个 item | 正常进入编辑模式 |
| 拖拽排序 | 编辑模式下拖拽 item | 正常排序 |
| 空列表 | 无 ETF 时下拉 | 不崩溃，正常刷新（无数据变化） |
| 网络断开 | 飞行模式下下拉 | 显示刷新动画，数据不变，不崩溃 |

**Step 3: PWA 验证（可选）**

在 iOS/Android 设备上以 PWA standalone 模式打开，验证：
- 浏览器原生下拉刷新被 `overscroll-y-contain` 抑制
- 自定义下拉刷新正常工作
- safe-area-inset 不影响指示器显示

---

## Task 6: 提交代码

**Step 1: 检查变更**

Run: `git diff --stat`
Expected: 涉及以下文件
- `frontend/hooks/use-pull-to-refresh.ts`（新建）
- `frontend/components/PullToRefreshIndicator.tsx`（新建）
- `frontend/lib/watchlist-context.tsx`（修改）
- `frontend/app/page.tsx`（修改）
- `docs/design/2026-02-06-watchlist-pull-to-refresh-design.md`（新建）

**Step 2: 提交**

```bash
git add frontend/hooks/use-pull-to-refresh.ts \
  frontend/components/PullToRefreshIndicator.tsx \
  frontend/lib/watchlist-context.tsx \
  frontend/app/page.tsx \
  docs/design/2026-02-06-watchlist-pull-to-refresh-design.md

git commit -m "feat(watchlist): add pull-to-refresh for real-time data update

- Add usePullToRefresh custom hook with touch gesture state machine
- Add PullToRefreshIndicator component with pull/threshold/refreshing/complete states
- Add refresh() method to WatchlistContext (cloud + local dual mode)
- Integrate into watchlist page with scroll container, disable during search/edit
- Add design document"
```

---

## 回滚方案

如果需要回滚，执行：

```bash
git revert HEAD
```

或手动回退各文件：

```bash
git checkout HEAD~1 -- frontend/lib/watchlist-context.tsx frontend/app/page.tsx
rm frontend/hooks/use-pull-to-refresh.ts frontend/components/PullToRefreshIndicator.tsx
```

---

*最后更新: 2026-02-06*
