# 确认对话框开发计划

## 目标
将设置页面中原生的 `window.confirm()` 替换为符合应用 "App Shell" 设计语言的自定义模态对话框 (Modal)。

## 1. 创建组件: `ConfirmationDialog`
**文件**: `frontend/components/ConfirmationDialog.tsx`

**规格**:
- **遮罩层 (Backdrop)**: 固定覆盖层，使用 `bg-black/50` 和 `backdrop-blur-sm`。
- **容器 (Container)**: 居中显示，`rounded-xl`, `bg-card`, `shadow-2xl`。
- **内容**:
  - 标题 (粗体, 大号)
  - 描述 (柔和色调, 小号)
  - 操作按钮 (取消 / 确认)
- **Props**:
  - `isOpen`: boolean
  - `title`: string
  - `description`: string
  - `confirmLabel`: string (默认: "确认")
  - `cancelLabel`: string (默认: "取消")
  - `onConfirm`: () => void
  - `onCancel`: () => void
  - `variant`: 'default' | 'destructive' (影响确认按钮颜色)

## 2. 更新设置页面
**文件**: `frontend/app/settings/page.tsx`

**变更**:
- 引入 `ConfirmationDialog` 组件。
- 添加状态: `const [showClearCacheDialog, setShowClearCacheDialog] = useState(false)`.
- 替换 `confirm()` 逻辑:
  - 点击按钮时设置 `showClearCacheDialog(true)`。
  - 对话框的 `onConfirm` 触发 `localStorage.clear()` 并刷新页面。
- 在 JSX 底部渲染对话框组件。

## 3. 样式细节
- **确认按钮 (Destructive)**: `bg-destructive text-destructive-foreground`
- **取消按钮**: `bg-secondary text-secondary-foreground`
- **动画**: 简单的透明度/缩放过渡 (可选，或使用条件渲染)。

## 4. 验证
- 验证点击 "清除缓存" 时对话框是否出现。
- 验证 "取消" 按钮能否关闭对话框且不执行操作。
- 验证 "确认" 按钮能否清除缓存并刷新页面。
- 检查深色模式 (Dark Mode) 下的显示效果。

---

# 自选页面编辑与长按拖拽排序功能计划

## 目标
为自选列表添加编辑模式，支持删除操作和基于长按拖拽的自定义排序功能。新增项自动置顶，排序结果需持久化到本地及云端。

## 1. 后端功能扩展 (API)
**文件**: `backend/app/models/user.py`, `backend/app/api/v1/endpoints/watchlist.py`

- **模型更新**:
  - `Watchlist` 表增加 `sort_order` (Integer) 字段，默认 0。
- **接口调整**:
  - `GET /watchlist/`: 修改查询逻辑，按 `sort_order ASC` 排序。
  - `POST /watchlist/{code}` (添加): 查询当前用户最小 `sort_order`，新项设为 `min_order - 1` (确保置顶)。
- **新增接口**:
  - `PUT /watchlist/reorder`: 接收 JSON `["code1", "code2", ...]`，事务性批量更新 `sort_order`。

## 2. 前端 Hook 增强
**文件**: `frontend/hooks/use-watchlist.ts`

- **新增方法**: `reorder(newOrderCodes: string[])`。
- **本地模式**: 更新 `localStorage` 存储的数组顺序。
- **云端模式**: 乐观更新本地 State，同时异步调用 `PUT /reorder` 接口。
- **现有逻辑优化**: 
  - `add` 方法确保新元素插入数组头部 (Index 0)。
  - `remove` 方法保持立即执行。

## 3. 前端 UI 实现
**文件**: `frontend/app/page.tsx`, `frontend/components/SortableETFItem.tsx` (新增)

- **依赖**: 安装 `@dnd-kit/core`, `@dnd-kit/sortable`, `@dnd-kit/utilities`。
- **状态管理**:
  - 新增 `isEditing` 状态。
  - 顶部按钮: 默认显示 `Edit3` 图标，`isEditing=true` 时显示 "完成" 文本。
- **长按拖拽 (SortableContext)**:
  - 使用 `PointerSensor`，配置 `activationConstraint: { delay: 250, tolerance: 5 }` (长按 250ms 触发)。
  - **震动反馈**: `onDragStart` 时调用 `navigator.vibrate(10)`。
  - **拖拽结束**: `onDragEnd` 时获取新顺序并调用 `hook.reorder()`。
- **列表项组件 (`SortableETFItem`)**:
  - **正常模式**: 保持 `Link` 跳转。
  - **编辑模式**:
    - 禁用跳转。
    - 左侧显示红色删除图标 (点击立即删除)。
    - 右侧显示拖拽手柄图标 (视觉引导)。
    - 整行支持长按触发拖拽。
    - 拖拽时的样式: 增加阴影 (Shadow-lg)，轻微放大，背景色调整。

## 4. 验证与交互
- **新增项置顶**: 添加新 ETF，确认出现在列表首位。
- **编辑模式**: 点击编辑按钮进入/退出模式正确。
- **删除**: 编辑模式下点击左侧红点立即删除行。
- **拖拽排序**:
  - 长按 250ms 后触发拖拽，手机震动。
  - 拖拽过程中列表平滑让位。
  - 松手后位置固定，刷新页面/重新登录后顺序保持。
- **云端同步**: 登录状态下，在一端调整顺序，另一端刷新后顺序同步。

---

# ETF 详情页指标动态同步计划

## 目标
实现详情页核心指标（CAGR、最大回撤、波动率）与图表上方选择的时间段（1y/3y/5y/all）实时联动，确保展示的数据与图表区间逻辑一致。

## 1. 后端 API 调整
**文件**: `backend/app/api/v1/endpoints/etf.py`

- **Update `get_etf_metrics`**:
  - 增加 `period` 参数 (可选值: "1y", "3y", "5y", "all")。
  - 逻辑变更:
    - 接收 `period` 参数。
    - 根据参数计算 `start_date`。
    - 对历史数据 `DataFrame` 进行切片。
    - 基于切片后的数据计算 Total Return, CAGR, MaxDrawdown, Volatility。
    - 确保 `mdd_date` 在切片范围内。

## 2. 前端状态提升与重构
**文件**: `frontend/app/etf/[code]/page.tsx`

- **状态管理**:
  - 新增 `period` 状态 (State): `const [period, setPeriod] = useState("5y")`.
  - `metrics` 数据请求需依赖 `period` 状态。
- **交互逻辑**:
  - 当 `period` 改变时:
    - 重新 fetch `/etf/{code}/metrics?period={period}`。
    - 指标卡片区域显示局部 Loading 状态。

## 3. 图表组件改造
**文件**: `frontend/components/ETFChart.tsx`

- **Props 变更**:
  - 移除内部 `period` 状态。
  - 新增 Props: `period: string`, `onPeriodChange: (p: string) => void`.
- **功能**:
  - 点击时间切换按钮时，调用 `onPeriodChange`。
  - 接收外部 `period` prop 控制图表数据过滤范围。

## 4. 验证
- **联动性**: 切换到 "1年" 时，图表变更为1年试图，同时下方 "最大回撤" 等指标数值发生变化。
- **数据准确**: 确保 "1年" 的最大回撤不是历史最大回撤，而是最近1年的最大回撤。
- **加载体验**: 切换时无明显页面闪烁，指标数据更新流畅。
