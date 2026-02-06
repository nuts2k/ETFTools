# Watchlist 下拉刷新 - 执行计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为自选列表页面添加下拉刷新功能，刷新行情价格和所有指标数据。

**Architecture:** 自定义 `usePullToRefresh` Hook + `PullToRefreshIndicator` 组件 + WatchlistContext `refresh()` 方法。

**Tech Stack:** React 19, TypeScript, Tailwind CSS, Next.js 16 (App Router)

**Design Doc:** `docs/design/2026-02-06-watchlist-pull-to-refresh-design.md`

---

## Task 1: WatchlistContext 添加 `refresh()` 方法

**Files:**
- Modify: `frontend/lib/watchlist-context.tsx`

**Step 1: 扩展接口和导入**

在 `WatchlistContextType` 接口添加 `refresh: () => Promise<void>`。

添加导入：
```typescript
import { type ETFItem, API_BASE_URL, fetchClient } from "@/lib/api";
import type { ETFDetail, ETFMetrics } from "@/lib/api";
```

**Step 2: 实现 `refresh` 和 `refreshLocal` 函数**

在 `isWatched` 函数之后添加：

- `refresh()`: Cloud 模式重新调用 `GET /watchlist/`；否则调用 `refreshLocal()`
- `refreshLocal()`: 对每个 item 并行调用 `GET /etf/{code}/info` + `GET /etf/{code}/metrics?period=5y`，用 `Promise.allSettled` 容错，失败项保留旧数据，更新后写入 localStorage

具体代码参见设计文档 Task 1 Step 3-4。

**Step 3: 更新 Provider value**

将 `refresh` 添加到 `<WatchlistContext.Provider value={...}>`。

**Step 4: 验证**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无错误输出

---

## Task 2: 创建 `usePullToRefresh` Hook

**Files:**
- Create: `frontend/hooks/use-pull-to-refresh.ts`

**核心实现要点（详见设计文档 Task 2）：**

1. **Hook 签名**: 接收 `onRefresh`, `scrollRef`, `threshold`(80), `maxPull`(120), `cooldown`(3000ms), `disabled`
2. **返回值**: `{ pullDistance: number, state: PullState }`
3. **状态机**: `idle → pulling → threshold → refreshing → complete → idle`
4. **手势逻辑**:
   - 仅在 `scrollRef.current.scrollTop <= 0` 时激活
   - 10px 方向锁定（水平优先则放弃）
   - 阻力曲线: `delta * (1 - delta / (maxPull * 3))`
   - 跨越阈值时 `navigator.vibrate(10)`
5. **事件挂载**: `useEffect` 挂载原生 touch 事件到 `scrollRef.current`，touchmove 用 `{ passive: false }`
6. **保护**: 3s 冷却 + 15s `Promise.race` 超时
7. **cleanup**: useEffect 返回函数移除所有监听器

**验证:**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无错误输出

---

## Task 3: 创建 `PullToRefreshIndicator` 组件

**Files:**
- Create: `frontend/components/PullToRefreshIndicator.tsx`

**实现要点（详见设计文档 Task 3）：**

1. Props: `pullDistance`, `state`, `threshold`
2. 外层 div: `overflow-hidden`，高度 = pullDistance（idle 时为 0）
3. 拉动中禁用 CSS transition，释放后启用 `transition-all duration-300`
4. 使用 `RefreshCw`（lucide-react，已在 page.tsx 导入）和 `Check` 图标
5. 各状态视觉：pulling → 按进度旋转 + "下拉刷新"；threshold → 180° + "释放刷新"；refreshing → animate-spin + "正在刷新..."；complete → Check + "刷新完成"

**验证:**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无错误输出

---

## Task 4: 集成到 `page.tsx`

**Files:**
- Modify: `frontend/app/page.tsx`

**Step 1: 添加导入和 ref**

- react 导入中添加 `useRef`
- 导入 `usePullToRefresh` 和 `PullToRefreshIndicator`
- 从 `useWatchlist()` 解构 `refresh`

**Step 2: 添加 Hook 调用**

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

**Step 3: 改造滚动容器**

最外层 div 变更：
- `min-h-[100dvh]` → `h-[100dvh]`
- 添加 `ref={scrollRef}`, `overflow-y-auto`, `overscroll-y-contain`

**Step 4: 插入指示器**

在 `{!isSearchMode && (` 块内，status bar 之前插入 `<PullToRefreshIndicator>`。

**Step 5: 验证**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无错误输出

---

## Task 5: 文档同步更新（AGENTS.md 规范要求）

**Files:**
- Modify: `AGENTS.md`

根据 AGENTS.md 第 4.6 节文档更新检查清单，本次变更涉及"修改核心代码路径"和"新增功能特性"，需同步更新以下内容：

**Step 1: 更新第 2 节技术栈（第 24 行）**

将交互行从：
```
| **交互** | @dnd-kit, use-long-press | 拖拽排序、长按操作 |
```
改为：
```
| **交互** | @dnd-kit, use-long-press, use-pull-to-refresh | 拖拽排序、长按操作、下拉刷新 |
```

**Step 2: 更新第 5 节前端关键文件（第 166 行）**

将首页行从：
```
| **首页** | `frontend/app/page.tsx` | 自选列表、拖拽排序 |
```
改为：
```
| **首页** | `frontend/app/page.tsx` | 自选列表、拖拽排序、下拉刷新 |
```

在 `自选逻辑` 行之后添加两行：
```
| **下拉刷新 Hook** | `frontend/hooks/use-pull-to-refresh.ts` | 触摸手势状态机 |
| **下拉刷新指示器** | `frontend/components/PullToRefreshIndicator.tsx` | 下拉视觉反馈 |
```

---

## Task 6: 端到端验证

**Step 1: 启动服务**

Run: `./manage.sh start`
Expected: 前后端正常启动

**Step 2: 功能验证清单**

| 场景 | 操作 | 预期结果 |
|------|------|---------|
| 基本下拉刷新 | 列表顶部下拉超过阈值后释放 | 指示器动画，数据刷新，时间戳更新 |
| 未达阈值释放 | 下拉不到 80px 后释放 | 指示器回弹，不触发刷新 |
| 编辑模式禁用 | 编辑模式下下拉 | 不触发 |
| 搜索模式禁用 | 搜索模式下下拉 | 不触发 |
| 冷却机制 | 3 秒内再次下拉 | 不触发 |
| 列表中间下拉 | 滚动到中间后下拉 | 正常滚动 |
| 长按进入编辑 | 长按 item | 正常进入编辑模式 |
| 拖拽排序 | 编辑模式拖拽 | 正常排序 |
| 空列表 | 无 ETF 时下拉 | 不崩溃 |
| 网络断开 | 飞行模式下拉 | 动画正常，数据不变 |

---

## Task 7: 提交代码

**Step 1: 检查变更**

Run: `git diff --stat`

Expected 涉及文件：
- `frontend/hooks/use-pull-to-refresh.ts`（新建）
- `frontend/components/PullToRefreshIndicator.tsx`（新建）
- `frontend/lib/watchlist-context.tsx`（修改）
- `frontend/app/page.tsx`（修改）
- `AGENTS.md`（修改）
- `docs/design/2026-02-06-watchlist-pull-to-refresh-design.md`（新建）
- `docs/implementation/2026-02-06-watchlist-pull-to-refresh-plan.md`（新建）

**Step 2: 提交**

```bash
git add frontend/hooks/use-pull-to-refresh.ts \
  frontend/components/PullToRefreshIndicator.tsx \
  frontend/lib/watchlist-context.tsx \
  frontend/app/page.tsx \
  AGENTS.md \
  docs/design/2026-02-06-watchlist-pull-to-refresh-design.md \
  docs/implementation/2026-02-06-watchlist-pull-to-refresh-plan.md

git commit -m "feat(watchlist): add pull-to-refresh for real-time data update

- Add usePullToRefresh custom hook with touch gesture state machine
- Add PullToRefreshIndicator component with visual feedback
- Add refresh() method to WatchlistContext (cloud + local dual mode)
- Integrate into watchlist page with scroll container
- Update AGENTS.md tech stack and key paths
- Add design and implementation docs"
```

---

## 回滚方案

```bash
git revert HEAD
```

---

*最后更新: 2026-02-06*
