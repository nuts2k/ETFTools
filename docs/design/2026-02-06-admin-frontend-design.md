# 管理员前端界面设计文档

**Goal:** 为已实现的后端管理员 API 构建完整的前端管理界面，包括控制台首页、用户管理、系统配置，以及配套的 ActionSheet 和 Toast 通用组件。

**Architecture:** Hub + 子页面模式（`/admin` → `/admin/users`、`/admin/system`），复用现有 iOS 风格卡片 UI，移动端优先。

**Tech Stack:** React 19, TypeScript, Next.js 16 (App Router), Tailwind CSS, Lucide Icons

**前置依赖:** [管理系统设计](2026-02-04-admin-system-design.md)（后端 API 已全部实现）

---

## 1. 现状分析

### 1.1 后端 API 已就绪

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/admin/users` | 用户列表（支持 `is_admin`、`is_active` 筛选） |
| GET | `/api/v1/admin/users/{user_id}` | 用户详情 |
| POST | `/api/v1/admin/users/{user_id}/toggle-admin` | 切换管理员权限 |
| POST | `/api/v1/admin/users/{user_id}/toggle-active` | 启用/禁用用户 |
| GET | `/api/v1/admin/system/config` | 获取系统配置 |
| POST | `/api/v1/admin/system/config/registration` | 开关注册 |
| POST | `/api/v1/admin/system/config/max-watchlist` | 设置自选上限 |

### 1.2 前端已有基础

| 文件 | 状态 | 说明 |
|------|------|------|
| `lib/auth-context.tsx` | ✅ 已有 | User 接口已含 `is_admin`、`is_active` |
| `lib/admin-guard.ts` | ✅ 已有 | `isAdmin()` / `requireAdmin()` |
| `app/admin/page.tsx` | ⚠️ 骨架 | 仅有占位卡片，无实际功能 |
| `app/settings/page.tsx` | ✅ 已有 | 管理员入口（Shield 图标 + ChevronRight） |

### 1.3 需要新建

| 文件 | 说明 |
|------|------|
| `app/admin/users/page.tsx` | 用户管理页 |
| `app/admin/system/page.tsx` | 系统配置页 |
| `components/ActionSheet.tsx` | 底部操作面板（通用组件） |
| `components/Toast.tsx` | 轻量 Toast 通知（通用组件） |

---

## 2. 页面架构

### 2.1 路由结构

```
/admin              → 控制台首页（统计概览 + 导航入口）
/admin/users        → 用户管理（列表 + 筛选 + 操作）
/admin/system       → 系统配置（注册开关 + 自选上限）
```

### 2.2 导航模式

- 从设置页 → `/admin`（已有入口）
- `/admin` 内部通过列表行导航到子页面
- 所有子页面顶部有返回箭头（`ArrowLeft`），返回上一级
- 不在 BottomNav 中添加管理入口（低频功能，不占底栏位置）

---

## 3. 通用组件设计

### 3.1 ActionSheet（底部操作面板）

从屏幕底部滑出的操作菜单，适合移动端多选项操作场景。

**Props 设计：**

```typescript
interface ActionSheetAction {
  label: string
  icon?: LucideIcon
  variant?: "default" | "destructive"
  onPress: () => void
}

interface ActionSheetProps {
  isOpen: boolean
  title?: string           // 可选标题（如 "user1 的操作"）
  actions: ActionSheetAction[]
  onClose: () => void
}
```

**视觉规格：**
- 背景遮罩：`bg-black/40 backdrop-blur-sm`（与 ConfirmationDialog 一致）
- 面板：`bg-card rounded-t-2xl`，从底部滑入
- 操作行：`p-4 min-h-[56px]`，点击有 `active:bg-secondary/80` 反馈
- destructive 操作：文字 `text-destructive`
- 取消按钮：独立一组，与操作列表间隔 `gap-2`
- 使用 `createPortal` 渲染到 `document.body`（与 ConfirmationDialog 一致）

**交互：**
- 点击遮罩关闭
- 点击操作项后自动关闭
- 支持动画：`animate-in slide-in-from-bottom duration-200`

**布局示意：**

```
┌─────────────────────────┐
│                         │
│     （遮罩区域）          │
│                         │
├─────────────────────────┤  ← rounded-t-2xl
│  user1 的操作            │  ← title（可选）
│─────────────────────────│
│  🛡️ 设为管理员           │  ← action
│─────────────────────────│
│  🚫 禁用账户       (红色) │  ← destructive action
├─────────────────────────┤  ← gap-2 分隔
│  取消                    │  ← 独立取消按钮
└─────────────────────────┘
```

### 3.2 Toast 通知

操作完成后短暂出现的轻量提示，自动消失。

**方案选择：** 自行实现轻量版（不引入第三方库，保持依赖精简）

**API 设计：**

```typescript
// Toast Context 提供全局调用能力
interface ToastContextType {
  toast: (message: string, variant?: "success" | "error") => void
}

// 使用方式
const { toast } = useToast()
toast("已将 user1 设为管理员", "success")
toast("操作失败，请重试", "error")
```

**视觉规格：**
- 位置：屏幕顶部，`top-safe + 16px`，水平居中
- 样式：`bg-card rounded-xl shadow-lg ring-1 ring-border/50 px-4 py-3`
- success：左侧绿色 `CheckCircle` 图标
- error：左侧红色 `XCircle` 图标
- 自动消失：2.5 秒后 fade-out
- 同时只显示一条（新 toast 替换旧 toast）

**实现要点：**
- 通过 `ToastProvider` 包裹在 `layout.tsx` 中
- 使用 `createPortal` 渲染到 `document.body`
- 用 `setTimeout` 控制自动消失

---

## 4. 控制台首页（改造 `/admin`）

### 4.1 数据来源

复用现有 API，首页加载时并行请求：
- `GET /api/v1/admin/users` → 计算用户总数、管理员数
- `GET /api/v1/admin/system/config` → 获取注册状态、自选上限

> 不新增 dashboard 聚合接口，用户量小，两个请求足够。

### 4.2 页面布局

```
┌─────────────────────────┐
│  ← 返回    管理员控制台    │  ← sticky header
├─────────────────────────┤
│  ┌──────┐ ┌──────┐      │
│  │ 用户数 │ │ 管理员 │      │  ← 2x2 统计卡片
│  │  12   │ │   2  │      │
│  └──────┘ └──────┘      │
│  ┌──────┐ ┌──────┐      │
│  │ 注册  │ │ 自选上限│      │
│  │ 开放  │ │  100 │      │
│  └──────┘ └──────┘      │
├─────────────────────────┤
│  功能                    │  ← section header
│  ┌─────────────────────┐ │
│  │ 👥 用户管理       >  │ │  ← 导航行
│  │─────────────────────│ │
│  │ ⚙️ 系统设置       >  │ │
│  └─────────────────────┘ │
└─────────────────────────┘
```

### 4.3 统计卡片规格

- 容器：`grid grid-cols-2 gap-3`
- 单卡：`bg-card rounded-xl p-4 ring-1 ring-border/50`
- 标签：`text-xs text-muted-foreground`
- 数值：`text-2xl font-bold mt-1`
- 注册状态用颜色区分：开放 `text-green-500` / 关闭 `text-red-500`

### 4.4 返回导航

- 顶部 header 左侧添加 `ArrowLeft` 返回按钮
- 点击返回 `/settings`（管理入口来源）
- 样式与 ETF 详情页的返回按钮一致

---

## 5. 用户管理页（`/admin/users`）

### 5.1 筛选 Tab

顶部 Tab 切换，不用下拉选择：

```
[全部]  [管理员]  [已禁用]
```

- 选中态：`bg-primary text-primary-foreground rounded-lg`
- 未选中：`text-muted-foreground`
- 切换时调用 `GET /admin/users?is_admin=true` 或 `?is_active=false`

### 5.2 用户列表

每行显示：

```
┌─────────────────────────────┐
│  admin              🛡️ 管理员 │  ← 用户名 + 状态标签
│  注册于 2026-01-15            │  ← 注册时间
├─────────────────────────────┤
│  user1                ✅ 正常 │
│  注册于 2026-01-20            │
├─────────────────────────────┤
│  user2              🚫 已禁用 │
│  注册于 2026-02-01            │
└─────────────────────────────┘
```

**状态标签样式（pill badge）：**

| 状态 | 样式 |
|------|------|
| 管理员 | `bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400` |
| 正常 | `bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400` |
| 已禁用 | `bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400` |

通用：`rounded-full px-2 py-0.5 text-xs font-medium`

### 5.3 用户操作流程

```
点击用户行
    ↓
弹出 ActionSheet（底部操作面板）
    ├── "设为管理员" / "取消管理员"
    ├── "禁用账户" / "启用账户"  (destructive)
    └── "取消"
    ↓
选择操作
    ↓
弹出 ConfirmationDialog（二次确认）
    ↓
确认 → 调用 API → Toast 反馈
```

### 5.4 自我保护

- 当前登录的管理员自己的行：操作按钮 disabled 或不显示 ActionSheet
- 点击自己时显示 Toast 提示："无法修改自己的权限"

### 5.5 乐观更新

```
用户确认操作
    → UI 立即更新状态标签
    → 调用 API
        → 成功：Toast "已将 xxx 设为管理员"
        → 失败：回滚 UI + Toast "操作失败，请重试"
```

---

## 6. 系统配置页（`/admin/system`）

### 6.1 页面布局

复用设置页的 section + card 样式：

```
┌─────────────────────────┐
│  ← 返回    系统设置       │
├─────────────────────────┤
│  注册控制                 │  ← section header
│  ┌─────────────────────┐ │
│  │ 开放注册    [Toggle] │ │  ← 即时生效
│  └─────────────────────┘ │
│                          │
│  限制                    │
│  ┌─────────────────────┐ │
│  │ 自选上限     100  >  │ │  ← select 交互
│  └─────────────────────┘ │
└─────────────────────────┘
```

### 6.2 注册开关

- 使用 Toggle Switch 组件（自行实现，不引入库）
- 切换即时调用 `POST /admin/system/config/registration?enabled=true/false`
- 切换时 Toggle 立即响应（乐观更新），失败则回滚 + Toast 报错

**Toggle 视觉规格：**
- 尺寸：`w-11 h-6`
- 开启：`bg-primary`，圆点右移
- 关闭：`bg-muted`，圆点左移
- 过渡：`transition-all duration-200`

### 6.3 自选上限

- 复用设置页的 select 交互模式（隐藏 select + 显示文本 + ChevronRight）
- 选项：`50 / 100 / 200 / 500`
- 选择后调用 `POST /admin/system/config/max-watchlist?max_items=xxx`
- Toast 反馈

---

## 7. API 调用层

### 7.1 在 `lib/api.ts` 中新增管理员 API 函数

```typescript
// 用户管理
fetchAdminUsers(token, params?: { is_admin?: boolean, is_active?: boolean })
toggleUserAdmin(token, userId)
toggleUserActive(token, userId)

// 系统配置
fetchSystemConfig(token)
setRegistrationEnabled(token, enabled: boolean)
setMaxWatchlistItems(token, maxItems: number)
```

### 7.2 请求规范

- 所有管理员 API 请求携带 `Authorization: Bearer {token}`
- 统一错误处理：403 → 跳转首页 + Toast "权限不足"
- 使用 `fetch`（与现有代码一致，不引入 axios）

---

## 8. 修改文件清单

| 操作 | 文件 | 说明 |
|------|------|------|
| **新建** | `frontend/components/ActionSheet.tsx` | 底部操作面板通用组件 |
| **新建** | `frontend/components/Toast.tsx` | Toast 通知组件 + ToastProvider + useToast |
| **新建** | `frontend/app/admin/users/page.tsx` | 用户管理页 |
| **新建** | `frontend/app/admin/system/page.tsx` | 系统配置页 |
| **修改** | `frontend/app/admin/page.tsx` | 改造为统计概览 + 导航入口 |
| **修改** | `frontend/app/layout.tsx` | 添加 ToastProvider |
| **修改** | `frontend/lib/api.ts` | 新增管理员 API 函数 |
| **修改** | `docs/README.md` | 文档索引添加本设计文档 |

---

## 9. 实施顺序

| 阶段 | 任务 | 依赖 |
|------|------|------|
| **Task 1** | ActionSheet 组件 | 无 |
| **Task 2** | Toast 组件 + ToastProvider + layout.tsx 集成 | 无 |
| **Task 3** | `lib/api.ts` 新增管理员 API 函数 | 无 |
| **Task 4** | 控制台首页改造 | Task 3 |
| **Task 5** | 用户管理页 | Task 1, 2, 3 |
| **Task 6** | 系统配置页 | Task 2, 3 |
| **Task 7** | 更新 `docs/README.md` 文档索引 | 无 |

> Task 1、2、3 可并行开发，Task 4/5/6 依赖前三者。

---

## 10. 验证方式

### 10.1 功能验证

- [ ] 非管理员访问 `/admin` 被重定向到首页
- [ ] 控制台首页正确显示用户数、管理员数、注册状态、自选上限
- [ ] 用户管理页 Tab 筛选正常（全部/管理员/已禁用）
- [ ] 点击用户弹出 ActionSheet，操作后弹出 ConfirmationDialog
- [ ] 切换管理员/禁用用户后列表状态即时更新
- [ ] 不能对自己执行操作（Toast 提示）
- [ ] 系统配置页 Toggle 开关注册功能正常
- [ ] 系统配置页修改自选上限正常
- [ ] 所有操作有 Toast 反馈（成功/失败）
- [ ] API 失败时 UI 回滚 + 错误 Toast

### 10.2 UI/UX 验证

- [ ] 移动端（375px 宽度）布局正常，无溢出
- [ ] 暗色模式下所有组件显示正常
- [ ] ActionSheet 动画流畅，点击遮罩可关闭
- [ ] Toast 自动消失，不遮挡操作
- [ ] 返回导航正常工作
- [ ] 状态标签颜色在亮/暗模式下均可辨识

### 10.3 安全验证

- [ ] 前端权限守卫生效（非管理员无法访问管理页面）
- [ ] API 请求携带正确的 Authorization header
- [ ] Token 失效时正确跳转登录页

---

## 11. 不做的事情

- **不做** 系统监控页（预留，后续单独设计）
- **不做** 用户搜索（用户量小，Tab 筛选足够）
- **不做** 分页（用户量小，一次加载）
- **不做** 批量操作（逐个操作更安全）
- **不做** 独立 admin layout（复用主 layout）
- **不引入** 第三方 Toast 库（自行实现轻量版）

---

**最后更新：** 2026-02-06
