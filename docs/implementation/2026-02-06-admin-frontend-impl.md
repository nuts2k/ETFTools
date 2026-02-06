# 管理员前端界面 — 实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为已实现的后端管理员 API 构建完整的前端管理界面，包括通用组件（ActionSheet、Toast）和三个页面（控制台首页、用户管理、系统配置）。

**Architecture:** Hub + 子页面模式（`/admin` → `/admin/users`、`/admin/system`），复用现有 iOS 风格卡片 UI，移动端优先。

**Tech Stack:** React 19, TypeScript, Next.js 16 (App Router), Tailwind CSS, Lucide Icons

**设计文档:** [docs/design/2026-02-06-admin-frontend-design.md](../design/2026-02-06-admin-frontend-design.md)

**后端 API 状态:** 全部已实现（`backend/app/api/v1/endpoints/admin.py`）

---

## 修改文件清单

| 操作 | 文件 | Task | 说明 |
|------|------|------|------|
| **新建** | `frontend/components/ActionSheet.tsx` | Task 1 | 底部操作面板通用组件 |
| **新建** | `frontend/components/Toast.tsx` | Task 2 | Toast 通知 + ToastProvider + useToast |
| **修改** | `frontend/app/layout.tsx` | Task 2 | 添加 ToastProvider |
| **修改** | `frontend/lib/api.ts` | Task 3 | 新增管理员 API 函数 + 类型定义 |
| **修改** | `frontend/app/admin/page.tsx` | Task 4 | 改造为统计概览 + 导航入口 |
| **新建** | `frontend/app/admin/users/page.tsx` | Task 5 | 用户管理页 |
| **新建** | `frontend/app/admin/system/page.tsx` | Task 6 | 系统配置页 |
| **修改** | `docs/README.md` | Task 7 | 文档索引更新 |

> **并行提示：** Task 1、2、3 无依赖关系，可并行开发。Task 4/5/6 依赖前三者完成。

---

## Task 1: ActionSheet 通用组件

**Files:**
- Create: `frontend/components/ActionSheet.tsx`

**参考:** `frontend/components/ConfirmationDialog.tsx`（遮罩、createPortal、动画模式）

### 接口定义

```typescript
import { type LucideIcon } from "lucide-react"

interface ActionSheetAction {
  label: string
  icon?: LucideIcon
  variant?: "default" | "destructive"
  onPress: () => void
}

interface ActionSheetProps {
  isOpen: boolean
  title?: string
  actions: ActionSheetAction[]
  onClose: () => void
}
```

### 实现要点

1. **渲染方式：** `createPortal` 到 `document.body`（与 ConfirmationDialog 一致）
2. **遮罩：** `bg-black/40 backdrop-blur-sm`，点击关闭
3. **面板：** 从底部滑入，`bg-card rounded-t-2xl` + `ring-1 ring-border/50`
4. **操作行：** `p-4 min-h-[56px]`，带图标和文字，`active:bg-secondary/80` 反馈
5. **destructive 样式：** 文字 `text-destructive`
6. **取消按钮：** 独立一组，与操作列表间隔 `gap-2`，`bg-card rounded-2xl`
7. **动画：** `animate-in slide-in-from-bottom duration-200`
8. **body overflow：** 打开时 `overflow: hidden`，关闭时恢复（参考 ConfirmationDialog）
9. **点击操作项后：** 先调用 `onPress()`，再调用 `onClose()`

### 布局结构

```
<Portal>
  <div className="fixed inset-0 z-[60]">
    {/* 遮罩 */}
    <div onClick={onClose} />

    {/* 面板 - 底部定位 */}
    <div className="absolute bottom-0 left-0 right-0 pb-safe">
      {/* 操作列表 */}
      <div className="mx-3 bg-card rounded-2xl overflow-hidden ring-1 ring-border/50">
        {title && <div className="px-4 py-3 text-center text-sm text-muted-foreground">{title}</div>}
        {actions.map(action => (
          <button className="w-full p-4 flex items-center gap-3 ...">
            {action.icon && <Icon />}
            {action.label}
          </button>
        ))}
      </div>

      {/* 取消按钮 - 独立一组 */}
      <div className="mx-3 mt-2 mb-3">
        <button className="w-full bg-card rounded-2xl p-4 font-semibold ...">取消</button>
      </div>
    </div>
  </div>
</Portal>
```

### 验证

```bash
cd frontend && npx tsc --noEmit
```

### 提交

```bash
git add frontend/components/ActionSheet.tsx
git commit -m "feat(ui): add ActionSheet component for mobile bottom action menus"
```

---

## Task 2: Toast 通知组件

**Files:**
- Create: `frontend/components/Toast.tsx`
- Modify: `frontend/app/layout.tsx`

### 接口定义

```typescript
type ToastVariant = "success" | "error"

interface ToastContextType {
  toast: (message: string, variant?: ToastVariant) => void
}
```

### 实现要点

**Toast.tsx 包含三部分：**

1. **ToastProvider** — Context Provider，管理 toast 状态
   - 状态：`{ message: string, variant: ToastVariant, key: number } | null`
   - `key` 用于同一消息重复触发时重新触发动画
   - 新 toast 替换旧 toast（同时只显示一条）

2. **useToast** — Hook，返回 `{ toast }` 函数

3. **ToastContainer** — 渲染组件（在 Provider 内部渲染）
   - 位置：`fixed top-0 left-0 right-0 z-[70] pt-safe`，内部 `px-4 pt-4`
   - 样式：`bg-card rounded-xl shadow-lg ring-1 ring-border/50 px-4 py-3 max-w-sm mx-auto`
   - success 图标：`CheckCircle`（lucide），`text-green-500`
   - error 图标：`XCircle`（lucide），`text-red-500`
   - 自动消失：`setTimeout` 2500ms 后设为 null
   - 动画：`animate-in fade-in slide-in-from-top-2 duration-300`
   - 使用 `createPortal` 渲染到 `document.body`

### layout.tsx 修改

在 `frontend/app/layout.tsx` 中添加 `ToastProvider`。

**位置：** 包裹在 `ThemeProvider` 内部，`<main>` 外层：

```tsx
import { ToastProvider } from "@/components/Toast"

// 在 ThemeProvider 内部：
<ThemeProvider ...>
  <ToastProvider>
    <main className="min-h-[100dvh] pb-20">
      {children}
    </main>
    <BottomNav />
  </ToastProvider>
</ThemeProvider>
```

**原因：** ToastProvider 需要在 ThemeProvider 内部才能正确继承主题样式。

### 验证

```bash
cd frontend && npx tsc --noEmit
```

### 提交

```bash
git add frontend/components/Toast.tsx frontend/app/layout.tsx
git commit -m "feat(ui): add Toast notification component with ToastProvider"
```

---

## Task 3: 管理员 API 函数

**Files:**
- Modify: `frontend/lib/api.ts`

### 新增类型定义

在 `frontend/lib/api.ts` 文件末尾（`triggerAlertCheck` 函数之后）添加：

```typescript
// 管理员 API 类型
export interface AdminUser {
  id: number
  username: string
  is_admin: boolean
  is_active: boolean
  created_at: string
  settings: Record<string, any>
}

export interface SystemConfig {
  registration_enabled: boolean
  max_watchlist_items: number
}
```

### 新增 API 函数

紧接类型定义之后添加 6 个函数。遵循现有代码风格（`fetch` + `Authorization` header + 错误处理）。

```typescript
// ===== 管理员 API =====

export async function fetchAdminUsers(
  token: string,
  params?: { is_admin?: boolean; is_active?: boolean }
): Promise<AdminUser[]> {
  const searchParams = new URLSearchParams()
  if (params?.is_admin !== undefined) searchParams.set("is_admin", String(params.is_admin))
  if (params?.is_active !== undefined) searchParams.set("is_active", String(params.is_active))
  const qs = searchParams.toString()
  const response = await fetch(`${API_BASE_URL}/admin/users${qs ? `?${qs}` : ""}`, {
    headers: { Authorization: `Bearer ${token}` }
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "获取用户列表失败" }))
    throw new Error(error.detail || "获取用户列表失败")
  }
  return response.json()
}

export async function toggleUserAdmin(
  token: string,
  userId: number
): Promise<{ user_id: number; is_admin: boolean }> {
  const response = await fetch(`${API_BASE_URL}/admin/users/${userId}/toggle-admin`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` }
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "操作失败" }))
    throw new Error(error.detail || "操作失败")
  }
  return response.json()
}

export async function toggleUserActive(
  token: string,
  userId: number
): Promise<{ user_id: number; is_active: boolean }> {
  const response = await fetch(`${API_BASE_URL}/admin/users/${userId}/toggle-active`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` }
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "操作失败" }))
    throw new Error(error.detail || "操作失败")
  }
  return response.json()
}

export async function fetchSystemConfig(token: string): Promise<SystemConfig> {
  const response = await fetch(`${API_BASE_URL}/admin/system/config`, {
    headers: { Authorization: `Bearer ${token}` }
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "获取系统配置失败" }))
    throw new Error(error.detail || "获取系统配置失败")
  }
  return response.json()
}

export async function setRegistrationEnabled(
  token: string,
  enabled: boolean
): Promise<{ registration_enabled: boolean }> {
  const response = await fetch(`${API_BASE_URL}/admin/system/config/registration?enabled=${enabled}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` }
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "操作失败" }))
    throw new Error(error.detail || "操作失败")
  }
  return response.json()
}

export async function setMaxWatchlistItems(
  token: string,
  maxItems: number
): Promise<{ max_watchlist_items: number }> {
  const response = await fetch(`${API_BASE_URL}/admin/system/config/max-watchlist?max_items=${maxItems}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` }
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "操作失败" }))
    throw new Error(error.detail || "操作失败")
  }
  return response.json()
}
```

**注意：** 后端 `toggle-registration` 和 `set-max-watchlist` 使用 query parameter 传参（非 body），与后端 `admin.py` 的 `enabled: bool` 和 `max_items: int = Query(...)` 对应。

### 验证

```bash
cd frontend && npx tsc --noEmit
```

### 提交

```bash
git add frontend/lib/api.ts
git commit -m "feat(api): add admin API functions for user management and system config"
```

---

## Task 4: 控制台首页改造

**Files:**
- Modify: `frontend/app/admin/page.tsx`（完全重写）

**依赖:** Task 3（API 函数）

### 数据加载

页面加载时并行请求两个 API：

```typescript
const [users, setUsers] = useState<AdminUser[]>([])
const [config, setConfig] = useState<SystemConfig | null>(null)

useEffect(() => {
  if (!token || !isAdmin(user)) return
  Promise.all([
    fetchAdminUsers(token),
    fetchSystemConfig(token),
  ]).then(([usersData, configData]) => {
    setUsers(usersData)
    setConfig(configData)
  })
}, [token, user])
```

### 页面结构

```
sticky header（← 返回 + "管理员控制台"）
  ↓
2x2 统计卡片 grid
  - 用户总数（users.length）
  - 管理员数（users.filter(u => u.is_admin).length）
  - 注册状态（config.registration_enabled ? "开放" : "关闭"）
  - 自选上限（config.max_watchlist_items）
  ↓
功能导航 section
  - 用户管理 → /admin/users（Users 图标 + ChevronRight）
  - 系统设置 → /admin/system（Settings 图标 + ChevronRight）
```

### 样式规格

**Header：**
- 复用设置页 header 样式：`sticky top-0 z-40 bg-background/95 backdrop-blur-md pt-safe border-b border-border/50`
- 左侧 `ArrowLeft` 按钮，`onClick={() => router.push("/settings")}`

**统计卡片：**
- 容器：`grid grid-cols-2 gap-3`
- 单卡：`bg-card rounded-xl p-4 ring-1 ring-border/50`
- 标签：`text-xs text-muted-foreground`
- 数值：`text-2xl font-bold mt-1`
- 注册状态颜色：开放 `text-green-500` / 关闭 `text-red-500`

**导航行：**
- 复用设置页的 section + card 列表行样式
- `bg-card rounded-xl ring-1 ring-border/50 divide-y divide-border/50`
- 每行：`flex items-center gap-3 p-4 hover:bg-secondary/50 transition-colors`

### 验证

```bash
cd frontend && npx tsc --noEmit
```

### 提交

```bash
git add frontend/app/admin/page.tsx
git commit -m "feat(admin): redesign admin dashboard with stats overview and navigation"
```

---

## Task 5: 用户管理页

**Files:**
- Create: `frontend/app/admin/users/page.tsx`

**依赖:** Task 1（ActionSheet）、Task 2（Toast）、Task 3（API 函数）

**复用:** `frontend/components/ConfirmationDialog.tsx`（二次确认）、`frontend/lib/admin-guard.ts`（权限守卫）

### 权限守卫

与 `admin/page.tsx` 相同的模式：

```typescript
useEffect(() => {
  if (!isLoading && !isAdmin(user)) router.push("/")
}, [user, isLoading, router])

if (isLoading || !isAdmin(user)) return null
```

### 页面状态

```typescript
const [users, setUsers] = useState<AdminUser[]>([])
const [filter, setFilter] = useState<"all" | "admin" | "disabled">("all")
const [selectedUser, setSelectedUser] = useState<AdminUser | null>(null)  // ActionSheet 目标
const [confirmAction, setConfirmAction] = useState<{ user: AdminUser; action: "admin" | "active" } | null>(null)
```

### 数据加载

```typescript
const loadUsers = async () => {
  if (!token) return
  const params: { is_admin?: boolean; is_active?: boolean } = {}
  if (filter === "admin") params.is_admin = true
  if (filter === "disabled") params.is_active = false
  const data = await fetchAdminUsers(token, params)
  setUsers(data)
}

useEffect(() => { loadUsers() }, [token, filter])
```

### 页面结构

```
sticky header（← 返回 + "用户管理"）
  ↓
筛选 Tab 栏（全部 / 管理员 / 已禁用）
  ↓
用户列表（card 内 divide-y 分隔）
  每行：用户名 + 状态标签 + 注册时间
  点击行 → 弹出 ActionSheet
```

### 筛选 Tab 样式

```tsx
const tabs = [
  { key: "all", label: "全部" },
  { key: "admin", label: "管理员" },
  { key: "disabled", label: "已禁用" },
]
```

- 容器：`flex gap-2 px-4 py-3`
- 选中：`bg-primary text-primary-foreground rounded-lg px-3 py-1.5 text-sm font-medium`
- 未选中：`text-muted-foreground px-3 py-1.5 text-sm font-medium`

### 状态标签（pill badge）

通用样式：`rounded-full px-2 py-0.5 text-xs font-medium`

| 状态 | 亮色 | 暗色 |
|------|------|------|
| 管理员 | `bg-amber-100 text-amber-700` | `dark:bg-amber-900/30 dark:text-amber-400` |
| 正常 | `bg-green-100 text-green-700` | `dark:bg-green-900/30 dark:text-green-400` |
| 已禁用 | `bg-red-100 text-red-700` | `dark:bg-red-900/30 dark:text-red-400` |

**显示逻辑：** 优先显示"已禁用"（`!is_active`），其次"管理员"（`is_admin`），否则"正常"。

### 用户操作交互流程

**Step 1: 点击用户行**

- 如果是当前登录用户自己 → `toast("无法修改自己的权限", "error")`，不弹 ActionSheet
- 否则 → `setSelectedUser(user)`，打开 ActionSheet

**Step 2: ActionSheet 操作项**

根据目标用户状态动态生成：

```typescript
const actions: ActionSheetAction[] = [
  {
    label: selectedUser.is_admin ? "取消管理员" : "设为管理员",
    icon: Shield,
    onPress: () => setConfirmAction({ user: selectedUser, action: "admin" }),
  },
  {
    label: selectedUser.is_active ? "禁用账户" : "启用账户",
    icon: selectedUser.is_active ? UserX : UserCheck,
    variant: selectedUser.is_active ? "destructive" : "default",
    onPress: () => setConfirmAction({ user: selectedUser, action: "active" }),
  },
]
```

**Step 3: ConfirmationDialog 二次确认**

ActionSheet 选择操作后关闭，弹出 ConfirmationDialog：

```typescript
<ConfirmationDialog
  isOpen={!!confirmAction}
  title={confirmAction?.action === "admin"
    ? (confirmAction.user.is_admin ? "取消管理员权限" : "授予管理员权限")
    : (confirmAction?.user.is_active ? "禁用账户" : "启用账户")}
  description={`确定要对用户 "${confirmAction?.user.username}" 执行此操作吗？`}
  variant={confirmAction?.action === "active" && confirmAction.user.is_active ? "destructive" : "default"}
  onConfirm={handleConfirm}
  onCancel={() => setConfirmAction(null)}
/>
```

**Step 4: 乐观更新 + API 调用**

```typescript
const handleConfirm = async () => {
  if (!confirmAction || !token) return
  const { user: targetUser, action } = confirmAction
  setConfirmAction(null)

  // 乐观更新
  const prevUsers = [...users]
  setUsers(prev => prev.map(u => {
    if (u.id !== targetUser.id) return u
    return action === "admin"
      ? { ...u, is_admin: !u.is_admin }
      : { ...u, is_active: !u.is_active }
  }))

  try {
    if (action === "admin") {
      await toggleUserAdmin(token, targetUser.id)
      toast(targetUser.is_admin ? `已取消 ${targetUser.username} 的管理员权限` : `已将 ${targetUser.username} 设为管理员`, "success")
    } else {
      await toggleUserActive(token, targetUser.id)
      toast(targetUser.is_active ? `已禁用 ${targetUser.username}` : `已启用 ${targetUser.username}`, "success")
    }
  } catch (e) {
    // 回滚
    setUsers(prevUsers)
    toast(e instanceof Error ? e.message : "操作失败", "error")
  }
}
```

### 验证

```bash
cd frontend && npx tsc --noEmit
```

### 提交

```bash
git add frontend/app/admin/users/page.tsx
git commit -m "feat(admin): add user management page with filtering and role/status toggle"
```

---

## Task 6: 系统配置页

**Files:**
- Create: `frontend/app/admin/system/page.tsx`

**依赖:** Task 2（Toast）、Task 3（API 函数）

**参考:** `frontend/app/settings/page.tsx`（section + card 样式、select 交互模式）

### 页面状态

```typescript
const [config, setConfig] = useState<SystemConfig | null>(null)
const [loading, setLoading] = useState(true)
```

### 数据加载

```typescript
useEffect(() => {
  if (!token || !isAdmin(user)) return
  fetchSystemConfig(token)
    .then(setConfig)
    .finally(() => setLoading(false))
}, [token, user])
```

### 页面结构

```
sticky header（← 返回 + "系统设置"）
  ↓
注册控制 section
  ┌─────────────────────────┐
  │ 开放注册        [Toggle] │  ← 即时生效
  └─────────────────────────┘
  ↓
限制 section
  ┌─────────────────────────┐
  │ 自选上限         100  > │  ← select 交互
  └─────────────────────────┘
```

### Toggle Switch 实现

内联实现，不抽独立组件（仅此一处使用）：

```tsx
<button
  onClick={handleToggleRegistration}
  className={cn(
    "relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200",
    config.registration_enabled ? "bg-primary" : "bg-muted"
  )}
>
  <span className={cn(
    "inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform duration-200",
    config.registration_enabled ? "translate-x-6" : "translate-x-1"
  )} />
</button>
```

**Toggle 交互（乐观更新）：**

```typescript
const handleToggleRegistration = async () => {
  if (!config || !token) return
  const prev = config.registration_enabled
  setConfig({ ...config, registration_enabled: !prev })
  try {
    await setRegistrationEnabled(token, !prev)
    toast(!prev ? "已开放注册" : "已关闭注册", "success")
  } catch (e) {
    setConfig({ ...config, registration_enabled: prev })
    toast(e instanceof Error ? e.message : "操作失败", "error")
  }
}
```

### 自选上限 Select

复用设置页的隐藏 select 交互模式（参考 `settings/page.tsx:114-134`）：

```tsx
<div className="group relative flex items-center justify-between p-4 min-h-[56px]
     cursor-pointer hover:bg-secondary/50 transition-colors">
  <span className="text-base font-normal">自选上限</span>
  <div className="flex items-center gap-1">
    <select
      className="appearance-none bg-transparent ... absolute inset-0 w-full h-full opacity-0"
      value={config.max_watchlist_items}
      onChange={(e) => handleMaxWatchlistChange(Number(e.target.value))}
    >
      <option value={50}>50</option>
      <option value={100}>100</option>
      <option value={200}>200</option>
      <option value={500}>500</option>
    </select>
    <span className="text-muted-foreground text-sm pointer-events-none">
      {config.max_watchlist_items}
    </span>
    <ChevronRight className="h-5 w-5 text-muted-foreground/50" />
  </div>
</div>
```

**Select 交互（乐观更新）：**

```typescript
const handleMaxWatchlistChange = async (value: number) => {
  if (!config || !token) return
  const prev = config.max_watchlist_items
  setConfig({ ...config, max_watchlist_items: value })
  try {
    await setMaxWatchlistItems(token, value)
    toast(`自选上限已设为 ${value}`, "success")
  } catch (e) {
    setConfig({ ...config, max_watchlist_items: prev })
    toast(e instanceof Error ? e.message : "操作失败", "error")
  }
}
```

### 验证

```bash
cd frontend && npx tsc --noEmit
```

### 提交

```bash
git add frontend/app/admin/system/page.tsx
git commit -m "feat(admin): add system config page with registration toggle and watchlist limit"
```

---

## Task 7: 文档索引更新

**Files:**
- Modify: `docs/README.md`

### 修改内容

在 `docs/README.md` 的 design/ 文档列表中（`2026-02-04-admin-system-design.md` 行之后）添加：

```markdown
- `2026-02-06-admin-frontend-design.md` - 管理员前端界面设计
```

在 implementation/ 文档列表末尾添加：

```markdown
- `2026-02-06-admin-frontend-impl.md` - 管理员前端界面实现
```

### 提交

```bash
git add docs/README.md
git commit -m "docs: add admin frontend design and implementation docs to index"
```

---

## 最终验证清单

### 自动化验证

```bash
cd frontend && npx tsc --noEmit
```

### 手动验证

| # | 场景 | 预期结果 |
|---|------|---------|
| 1 | 非管理员访问 `/admin` | 重定向到首页 |
| 2 | 非管理员访问 `/admin/users` | 重定向到首页 |
| 3 | 管理员访问控制台首页 | 显示用户数、管理员数、注册状态、自选上限 |
| 4 | 点击"用户管理"导航 | 跳转到 `/admin/users` |
| 5 | 用户管理页 Tab 切换 | 筛选结果正确（全部/管理员/已禁用） |
| 6 | 点击非自己的用户行 | 弹出 ActionSheet |
| 7 | 点击自己的用户行 | Toast 提示"无法修改自己的权限" |
| 8 | ActionSheet 选择操作 | 弹出 ConfirmationDialog 二次确认 |
| 9 | 确认切换管理员权限 | 状态标签即时更新 + Toast 成功提示 |
| 10 | 确认禁用/启用用户 | 状态标签即时更新 + Toast 成功提示 |
| 11 | API 失败时 | UI 回滚 + Toast 错误提示 |
| 12 | 系统配置页 Toggle 注册开关 | 即时生效 + Toast 反馈 |
| 13 | 系统配置页修改自选上限 | 即时生效 + Toast 反馈 |
| 14 | 移动端 375px 宽度 | 所有页面布局正常，无溢出 |
| 15 | 暗色模式 | 所有组件、标签颜色正常显示 |
| 16 | ActionSheet 点击遮罩 | 正常关闭 |
| 17 | Toast 自动消失 | 2.5 秒后消失，不遮挡操作 |

---

*最后更新: 2026-02-06*
