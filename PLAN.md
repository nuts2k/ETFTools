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
