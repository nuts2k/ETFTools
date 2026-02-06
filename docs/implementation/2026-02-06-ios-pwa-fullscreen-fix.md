# iOS 26 PWA 浏览器控制条修复实现计划

## 问题描述

用户报告在 iOS 26 上以 PWA 方式运行时，有时最下方会显示出浏览器控制条。

**具体表现**：
- **触发条件**：切换页面时出现，在 watchlist 和搜索页面都会出现，但是在设置页面（保存到桌面的页面）没有
- **位置关系**：控制条显示在底部导航栏下方
- **安装方式**：通过 Safari 分享菜单添加到主屏幕

## 根因分析

经过代码探索和分析，发现项目缺少完整的 PWA 配置：

1. **缺少 `viewport-fit=cover`**：iOS 无法将应用扩展到安全区域，导致浏览器控制条出现
2. **缺少 manifest.json**：iOS 无法识别应用为标准 PWA
3. **缺少 Apple 专用 meta 标签**：没有 `apple-mobile-web-app-capable` 启用独立模式
4. **缺少 PWA 图标**：没有 Apple touch icons 用于主屏幕安装

## 解决方案概述

通过添加完整的 PWA 配置，使应用在 iOS 上以独立模式（standalone）运行，隐藏浏览器 UI。

**核心修改**：
1. 在 `layout.tsx` 中添加 `viewport-fit=cover` 和 Apple meta 标签
2. 创建 `manifest.json` 配置文件（`display: "standalone"`）
3. 创建 PWA 图标（192px, 512px, 180px）
4. 增强 CSS 安全区域工具类，添加 iOS 26.1 兼容性回退
5. 更新文档（AGENTS.md, README.md, 实现文档）

---

## 实施步骤

### 步骤 1：修改 layout.tsx - 添加 viewport-fit 和 Apple meta 标签

**文件**：`frontend/app/layout.tsx`

**修改 1 - viewport 配置（第 10-15 行）**：

当前代码：
```typescript
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
};
```

修改为：
```typescript
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: "cover", // 启用 iOS 全屏模式
};
```

**修改 2 - metadata 配置（第 17-20 行）**：

当前代码：
```typescript
export const metadata: Metadata = {
  title: "ETFTool (A股版)",
  description: "专业的 A 股 ETF 前复权收益分析工具",
};
```

修改为：
```typescript
export const metadata: Metadata = {
  title: "ETFTool (A股版)",
  description: "专业的 A 股 ETF 前复权收益分析工具",

  // Apple PWA 配置
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "ETFTool",
  },

  // Manifest 引用
  manifest: "/manifest.json",

  // 主题色
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f6f7f8" },
    { media: "(prefers-color-scheme: dark)", color: "#0f172a" },
  ],
};
```

**修改 3 - html lang 属性**：

当前代码（`layout.tsx` 第 31 行）：
```tsx
<html lang="en" suppressHydrationWarning>
```

修改为：
```tsx
<html lang="zh-CN" suppressHydrationWarning>
```

> 应用为中文界面，manifest 中也声明了 `"lang": "zh-CN"`，需保持一致。

**关键说明**：
- `viewportFit: "cover"` 是最关键的修改，允许应用扩展到整个屏幕
- `appleWebApp.capable: true` 启用独立模式（无浏览器 UI）
- `statusBarStyle: "black-translucent"` 使状态栏透明
- `lang="zh-CN"` 与 manifest 保持一致，有助于搜索引擎和辅助功能正确识别语言

---

### 步骤 2：创建 manifest.json

**文件**：`frontend/public/manifest.json`（新建）

```json
{
  "name": "ETFTool (A股版)",
  "short_name": "ETFTool",
  "description": "专业的 A 股 ETF 前复权收益分析工具",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#f6f7f8",
  "theme_color": "#1269e2",
  "orientation": "portrait-primary",
  "scope": "/",
  "icons": [
    {
      "src": "/icon-192.png",
      "sizes": "192x192",
      "type": "image/png",
      "purpose": "any"
    },
    {
      "src": "/icon-192-maskable.png",
      "sizes": "192x192",
      "type": "image/png",
      "purpose": "maskable"
    },
    {
      "src": "/icon-512.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "any"
    },
    {
      "src": "/icon-512-maskable.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "maskable"
    },
    {
      "src": "/apple-touch-icon.png",
      "sizes": "180x180",
      "type": "image/png"
    }
  ],
  "categories": ["finance", "productivity"],
  "lang": "zh-CN",
  "dir": "ltr"
}
```

**关键说明**：
- `display: "standalone"` 告诉 iOS 隐藏浏览器 UI
- `start_url: "/"` 确保应用从 watchlist 页面启动（解决设置页面问题）
- `orientation: "portrait-primary"` 匹配移动端优先设计

> ⚠️ **已知限制**：manifest 的 `background_color` 不支持 media query，只能设置一个值。暗色模式用户安装 PWA 时，启动画面（splash screen）会显示浅色背景 `#f6f7f8`，这是 Web App Manifest 规范的限制，暂无法解决。

---

### 步骤 3：创建 PWA 图标

**需要创建的图标文件**（位于 `frontend/public/`）：

1. **icon-192.png** (192x192px) - 标准 PWA 图标
2. **icon-192-maskable.png** (192x192px) - Maskable PWA 图标（内容集中在 80% 安全区域内）
3. **icon-512.png** (512x512px) - 高分辨率 PWA 图标
4. **icon-512-maskable.png** (512x512px) - 高分辨率 Maskable PWA 图标
5. **apple-touch-icon.png** (180x180px) - iOS 主屏幕图标

> ⚠️ **注意**：当前 `frontend/public/` 下没有 favicon.ico，只有 Next.js 默认的 SVG 文件，需要**从零设计**所有图标。

**设计要求**：
- 使用 ETF/股票市场主题图标（图表、趋势线或 "ETF" 文字）
- 遵循 iOS 图标设计规范（无透明度，圆角由 iOS 处理）
- 匹配应用配色方案：主蓝色 (#1269e2) 在浅色背景上
- 确保在浅色和深色模式下都有良好对比度
- **Maskable 图标**：内容必须集中在中心 80% 区域内，四周留出安全边距
- **Any 图标**：内容可以填满整个画布

**图标生成方法**：
- 使用 Figma、Sketch 等设计工具从零创建
- 使用 PWA Asset Generator 批量生成多尺寸
- 使用 [maskable.app](https://maskable.app/) 验证 maskable 图标的安全区域

**临时方案**：如果暂时没有专业图标，可以先使用简单的文字图标或占位图标，后续再优化。

---

### 步骤 4：增强 CSS 安全区域工具类

**文件**：`frontend/app/globals.css`

**修改位置**：第 106-124 行的 `@layer utilities` 部分

当前代码：
```css
@layer utilities {
  .pb-safe {
    padding-bottom: env(safe-area-inset-bottom);
  }
  .pt-safe {
    padding-top: env(safe-area-inset-top);
  }
  .no-scrollbar::-webkit-scrollbar {
    display: none;
  }
  .no-scrollbar {
    -ms-overflow-style: none;
    scrollbar-width: none;
  }
  .backface-hidden {
    -webkit-backface-visibility: hidden;
    backface-visibility: hidden;
  }
}
```

修改为：
```css
@layer utilities {
  .pb-safe {
    padding-bottom: env(safe-area-inset-bottom, 0px);
  }
  .pt-safe {
    padding-top: env(safe-area-inset-top, 0px);
  }
  /* iOS 26.1 回归问题的最小安全区域（备用方案，默认不启用） */
  /* 仅在 iOS 26.1 测试确认 safe-area-inset-bottom 返回 0px 时才使用 */
  .pb-safe-min {
    padding-bottom: max(env(safe-area-inset-bottom, 0px), 8px);
  }

  .no-scrollbar::-webkit-scrollbar {
    display: none;
  }
  .no-scrollbar {
    -ms-overflow-style: none;
    scrollbar-width: none;
  }
  .backface-hidden {
    -webkit-backface-visibility: hidden;
    backface-visibility: hidden;
  }
}
```

**关键说明**：
- 添加回退值 `0px` 防止 iOS 26.1 返回空值时的布局问题
- `pb-safe-min` 为备用方案，仅在 iOS 26.1 测试确认问题后才应用到 BottomNav
- 不预先添加 `pl-safe`/`pr-safe`/`p-safe` 等暂无使用场景的工具类，避免过度添加

**BottomNav 组件验证**：
- 文件：`frontend/components/BottomNav.tsx`
- 第 35 行已正确使用 `pb-safe` 类
- 如果 iOS 26.1 测试发现问题，可考虑改用 `pb-safe-min`

**详情页安全区域验证**：
- 文件：`frontend/app/etf/[code]/page.tsx`
- BottomNav 在详情页隐藏（`isDetailPage` 时 `return null`）
- 添加 `viewport-fit=cover` 后，详情页底部内容可能被 home indicator 遮挡
- **必须检查**：详情页底部是否有固定定位元素或内容需要添加 `pb-safe` 处理
- 如有浮动操作按钮或底部栏，确保其也使用 safe-area-inset

---

### 步骤 5：更新文档

#### 5.1 更新 AGENTS.md

**文件**：`AGENTS.md`

**修改 1 - 第 2 节技术栈速查表（约第 26 行后）**：

在表格中添加一行：
```markdown
| **PWA 支持** | manifest.json + Apple meta tags | iOS/Android 主屏幕安装 |
```

**修改 2 - 第 4.2 节 UI/UX 强制规范（约第 60 行后）**：

在 "移动端优先" 规范后添加：
```markdown
⚠️ **【强制】PWA 全屏模式**
- iOS 必须配置 `viewport-fit=cover` 和 `apple-mobile-web-app-capable`
- 所有固定定位元素必须使用 safe-area-inset 避免被系统 UI 遮挡
```

**修改 3 - 第 5 节前端关键文件表**：

在前端关键文件表中添加：
```markdown
| **PWA 配置** | `frontend/public/manifest.json` | PWA 清单、图标、主屏幕安装 |
```

**修改 4 - 第 7 节关键配置文件表**：

在配置文件表中添加：
```markdown
| **PWA 清单** | `frontend/public/manifest.json` | PWA 名称、图标、显示模式、主题色 |
```

#### 5.2 更新 README.md

**文件**：`README.md`

在"功能特性"部分添加：
```markdown
- 📱 PWA 支持，可安装到主屏幕
```

---

## 验证计划

### 本地验证

1. **构建测试**：
   ```bash
   cd frontend
   npm run build
   ```
   验证无构建错误

2. **Manifest 可访问性**：
   - 启动开发服务器
   - 访问 `http://localhost:3000/manifest.json`
   - 验证 JSON 格式正确

3. **图标文件检查**：
   - 验证 `public/icon-192.png` 存在
   - 验证 `public/icon-192-maskable.png` 存在
   - 验证 `public/icon-512.png` 存在
   - 验证 `public/icon-512-maskable.png` 存在
   - 验证 `public/apple-touch-icon.png` 存在
   - 使用 [maskable.app](https://maskable.app/) 验证 maskable 图标安全区域

### iOS 设备测试（关键）

**测试前准备**：
1. 删除现有主屏幕应用
2. 清除 Safari 缓存（设置 > Safari > 清除历史记录和网站数据）
3. 如果可能，重启设备

**测试步骤**：
1. **安装测试**：
   - 在 Safari 中打开应用
   - 点击分享按钮
   - 选择"添加到主屏幕"
   - 验证图标和名称显示正确

2. **独立模式测试**：
   - 从主屏幕启动应用
   - ✅ 验证无浏览器控制条
   - ✅ 验证无顶部 URL 栏
   - ✅ 验证状态栏透明（内容可见）

3. **导航测试**：
   - 在 watchlist、搜索、设置页面间切换
   - ✅ 验证浏览器控制条不出现
   - ✅ 验证底部导航栏位置正确
   - ✅ 验证底部导航不与 home indicator 重叠

4. **详情页测试**（BottomNav 隐藏的页面）：
   - 进入 ETF 详情页 (`/etf/[code]`)
   - ✅ 验证底部内容不被 home indicator 遮挡
   - ✅ 验证浮动操作按钮/底部栏正确处理安全区域
   - ✅ 验证页面滚动到底部时内容完整可见

5. **安全区域测试**：
   - ✅ 验证内容不被刘海/Dynamic Island 遮挡
   - ✅ 验证底部导航不与 home indicator 重叠
   - 测试横屏模式（如果支持）

**iOS 26 特定测试**：
- 在 iOS 26.0 和 26.1 上测试（如果可能）
- 使用 Safari Web Inspector 检查 `safe-area-inset-bottom` 值
- 如果返回 0px，验证 `pb-safe-min` 回退方案生效

### 调试方法

如果浏览器控制条仍然出现：

1. **Safari Web Inspector**：
   - 连接 iPhone 到 Mac
   - Safari > 开发 > [您的 iPhone] > [您的应用]
   - 控制台：检查错误
   - 控制台：运行 `getComputedStyle(document.documentElement).getPropertyValue('--safe-area-inset-bottom')`

2. **验证 meta 标签**：
   - 在 Web Inspector 中检查 `<head>` 部分
   - 验证 `<meta name="apple-mobile-web-app-capable" content="yes">` 存在
   - 验证 `<meta name="viewport" content="...viewport-fit=cover...">` 存在

3. **检查 manifest**：
   - 在 Safari 中直接访问 `/manifest.json`
   - 验证 JSON 有效且 `display: "standalone"` 存在

4. **强制重新安装**：
   - iOS 有时会缓存 PWA 配置
   - 删除应用 → 清除 Safari 缓存 → 重启 iPhone → 重新安装

---

## 成功标准

### 必须达成（P0）
- ✅ 从主屏幕启动时不出现浏览器控制条
- ✅ 应用以独立模式运行（无 Safari UI）
- ✅ 底部导航正确处理安全区域
- ✅ 状态栏透明，内容可见

### 应该达成（P1）
- ✅ 主屏幕显示正确的应用图标
- ✅ 页面导航流畅，不触发浏览器 UI
- ✅ 在 iOS 26.0 和 26.1 上都能正常工作

### 可选达成（P2）
- ⭕ 应用启动时显示启动画面
- ⭕ 离线支持（延后）
- ⭕ 为用户提供安装提示

---

## 关键文件清单

### 需要修改的文件

1. **`frontend/app/layout.tsx`**
   - 添加 `viewportFit: "cover"`
   - 添加 Apple PWA meta 标签
   - 修改 `html lang="en"` → `lang="zh-CN"`

2. **`frontend/app/globals.css`**
   - 增强安全区域工具类
   - 添加 iOS 26.1 兼容性回退

3. **`AGENTS.md`**
   - 更新第 2 节技术栈表格（新增 PWA 支持）
   - 更新第 4.2 节添加 PWA 强制规范
   - 更新第 5 节前端关键文件表（新增 manifest.json）
   - 更新第 7 节关键配置文件表（新增 manifest.json）

4. **`README.md`**
   - 添加 PWA 功能特性

### 需要创建的文件

1. **`frontend/public/manifest.json`**
   - PWA 配置文件

2. **`frontend/public/icon-192.png`**
   - 192x192px PWA 图标（purpose: any）

3. **`frontend/public/icon-192-maskable.png`**
   - 192x192px Maskable PWA 图标（内容集中在 80% 安全区域）

4. **`frontend/public/icon-512.png`**
   - 512x512px PWA 图标（purpose: any）

5. **`frontend/public/icon-512-maskable.png`**
   - 512x512px Maskable PWA 图标（内容集中在 80% 安全区域）

6. **`frontend/public/apple-touch-icon.png`**
   - 180x180px iOS 主屏幕图标

---

## 实施顺序

1. ✅ **创建 PWA 图标**（icon-192.png, icon-512.png, apple-touch-icon.png）
2. ✅ **创建 manifest.json**
3. ✅ **修改 layout.tsx**（viewport-fit 和 Apple meta 标签）
4. ✅ **修改 globals.css**（安全区域回退）
5. ✅ **本地测试**（构建、manifest 可访问性）
6. ✅ **更新文档**（AGENTS.md, README.md）
7. ✅ **提交所有变更**（单个 commit，符合 AGENTS.md 4.6 规范）
8. ✅ **部署到生产环境**
9. ✅ **iOS 设备测试**（完整测试清单）
10. ✅ **监控和迭代**（关注 iOS 26.1 特定问题）

---

## 风险评估

### 高风险

1. **iOS 26.1 safe-area-inset 回归**
   - **风险**：iOS 26.1 可能返回 0px
   - **缓解**：添加 `pb-safe-min` 回退方案
   - **监控**：在多个 iOS 版本上测试

2. **图标质量**
   - **风险**：低质量图标影响用户体验
   - **缓解**：使用专业设计工具
   - **回退**：可先使用简单文字图标，后续优化

### 中风险

1. **Manifest 缓存**
   - **风险**：iOS 可能缓存旧配置，需要重新安装
   - **缓解**：提供清晰的重新安装说明
   - **沟通**：通知用户更新后需重新安装 PWA

2. **主题色不匹配**
   - **风险**：主题色与实际应用外观不符
   - **缓解**：使用 globals.css 中的精确颜色
   - **测试**：在浅色和深色模式下验证

### 低风险

1. **构建大小增加**
   - **风险**：添加图标增加包大小
   - **影响**：约 50KB（3 个图标）
   - **可接受**：PWA 优势远超小幅增加

---

## 回滚计划

如果部署后出现问题：

1. **立即回滚**：恢复包含 PWA 变更的提交
2. **快速修复**：如果导致布局问题，移除 `viewport-fit=cover`
3. **部分回滚**：保留 manifest 但移除 Apple meta 标签
4. **用户沟通**：通知用户暂时使用 Safari 而非 PWA

---

## 参考资料

- [iOS PWA 支持文档](https://webkit.org/blog/) - WebKit 官方博客
- [Next.js PWA 配置](https://nextjs.org/docs) - Next.js 16 官方文档
- [PWA Manifest 规范](https://www.w3.org/TR/appmanifest/) - W3C PWA manifest 标准
- [viewport-fit 和 safe-area-inset](https://webkit.org/blog/7929/designing-websites-for-iphone-x/) - WebKit 关于 iOS 安全区域的文档

---

**最后更新**: 2026-02-06
