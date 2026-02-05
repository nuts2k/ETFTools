# Watchlist 紧凑指标显示 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 watchlist 卡片中同时显示趋势、温度、ATR 和回撤四个指标，保持单行紧凑布局。

**Architecture:** 修改 `SortableWatchlistItem.tsx` 组件，将四个指标整合到一行显示，使用 `flex-wrap` 实现窄屏自动换行，通过分隔符和颜色区分不同类型指标。

**Tech Stack:** React, TypeScript, Tailwind CSS

---

## 设计规范

### 最终效果
```
↗️ 连涨3周 · 🔥 温度75 · 波动 0.065 · -10.5%
```

### 指标显示规则
1. **周趋势** (`TrendIndicator`): 仅当 `|consecutive_weeks| >= 2` 时显示
2. **温度** (`TemperatureIndicator`): 有数据时始终显示
3. **ATR/波动** (`VolatilityIndicator`): 有数据时始终显示，标签简化为"波动"
4. **回撤** (`DrawdownIndicator`): 有数据时始终显示，省略标签，用颜色表示

### 分隔符
- 使用淡色圆点 `·` 分隔各指标
- 分隔符颜色: `text-muted-foreground/30`

### 颜色规范
- 趋势上涨: `text-up` (红色)
- 趋势下跌: `text-down` (绿色)
- 温度 hot: `text-up`
- 温度 warm: `text-orange-500`
- 温度 cool: `text-blue-400`
- 温度 freezing: `text-blue-500`
- ATR/波动: `text-muted-foreground`
- 回撤负值: `text-down`
- 回撤零/正: `text-muted-foreground`

---

## Task 1: 添加波动率指示器组件

**Files:**
- Modify: `frontend/components/SortableWatchlistItem.tsx:63-89`

**Step 1: 在 TemperatureIndicator 组件后添加 VolatilityIndicator 组件**

在第 89 行（TemperatureIndicator 组件结束后）添加新组件：

```tsx
// 波动率指示器组件
function VolatilityIndicator({ 
  atr 
}: { 
  atr?: number | null;
}) {
  if (atr === null || atr === undefined) {
    return null;
  }
  
  return (
    <span className="inline-flex items-center gap-1 text-[10px] font-medium text-muted-foreground">
      <span>波动</span>
      <span className="tabular-nums">{atr.toFixed(3)}</span>
    </span>
  );
}
```

**Step 2: 验证组件语法正确**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无错误输出

---

## Task 2: 添加回撤指示器组件

**Files:**
- Modify: `frontend/components/SortableWatchlistItem.tsx` (在 VolatilityIndicator 后)

**Step 1: 添加 DrawdownIndicator 组件**

```tsx
// 回撤指示器组件
function DrawdownIndicator({ 
  drawdown 
}: { 
  drawdown?: number | null;
}) {
  if (drawdown === null || drawdown === undefined) {
    return null;
  }
  
  const isNegative = drawdown < 0;
  const displayValue = (drawdown * 100).toFixed(1);
  
  return (
    <span className={cn(
      "inline-flex items-center text-[10px] font-medium tabular-nums",
      isNegative ? "text-down" : "text-muted-foreground"
    )}>
      {isNegative ? "" : "+"}{displayValue}%
    </span>
  );
}
```

**Step 2: 验证组件语法正确**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无错误输出

---

## Task 3: 添加分隔符组件

**Files:**
- Modify: `frontend/components/SortableWatchlistItem.tsx` (在 DrawdownIndicator 后)

**Step 1: 添加 Separator 组件**

```tsx
// 指标分隔符
function IndicatorSeparator() {
  return <span className="text-muted-foreground/30 text-[10px]">·</span>;
}
```

**Step 2: 验证组件语法正确**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无错误输出

---

## Task 4: 重构指标显示区域

**Files:**
- Modify: `frontend/components/SortableWatchlistItem.tsx:145-166`

**Step 1: 替换现有的指标显示区域**

将第 145-166 行的代码替换为：

```tsx
        {/* Compact Indicators Row */}
        <div className="flex items-center gap-1.5 mt-2 flex-wrap text-[10px]">
          <TrendIndicator 
            direction={etf.weekly_direction} 
            weeks={etf.consecutive_weeks} 
          />
          {etf.weekly_direction && Math.abs(etf.consecutive_weeks || 0) >= 2 && 
            (etf.temperature_score !== null && etf.temperature_score !== undefined) && 
            <IndicatorSeparator />
          }
          <TemperatureIndicator 
            score={etf.temperature_score} 
            level={etf.temperature_level} 
          />
          {(etf.temperature_score !== null && etf.temperature_score !== undefined) && 
            (etf.atr !== null && etf.atr !== undefined) && 
            <IndicatorSeparator />
          }
          <VolatilityIndicator atr={etf.atr} />
          {(etf.atr !== null && etf.atr !== undefined) && 
            (etf.current_drawdown !== null && etf.current_drawdown !== undefined) && 
            <IndicatorSeparator />
          }
          <DrawdownIndicator drawdown={etf.current_drawdown} />
        </div>
```

**Step 2: 验证组件语法正确**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无错误输出

---

## Task 5: 简化分隔符逻辑

**Files:**
- Modify: `frontend/components/SortableWatchlistItem.tsx`

**Step 1: 创建辅助函数简化分隔符逻辑**

在组件文件顶部（导入语句后）添加辅助函数：

```tsx
// 辅助函数：检查指标是否有值
function hasValue(value: number | null | undefined): boolean {
  return value !== null && value !== undefined;
}
```

**Step 2: 重构指标显示区域使用更简洁的逻辑**

```tsx
        {/* Compact Indicators Row */}
        <div className="flex items-center gap-1.5 mt-2 flex-wrap text-[10px]">
          {/* 收集所有要显示的指标 */}
          {(() => {
            const indicators: React.ReactNode[] = [];
            
            // 趋势指标（仅 >=2 周显示）
            if (etf.weekly_direction && Math.abs(etf.consecutive_weeks || 0) >= 2) {
              indicators.push(
                <TrendIndicator 
                  key="trend"
                  direction={etf.weekly_direction} 
                  weeks={etf.consecutive_weeks} 
                />
              );
            }
            
            // 温度指标
            if (hasValue(etf.temperature_score) && etf.temperature_level) {
              indicators.push(
                <TemperatureIndicator 
                  key="temp"
                  score={etf.temperature_score} 
                  level={etf.temperature_level} 
                />
              );
            }
            
            // 波动率指标
            if (hasValue(etf.atr)) {
              indicators.push(
                <VolatilityIndicator key="atr" atr={etf.atr} />
              );
            }
            
            // 回撤指标
            if (hasValue(etf.current_drawdown)) {
              indicators.push(
                <DrawdownIndicator key="dd" drawdown={etf.current_drawdown} />
              );
            }
            
            // 用分隔符连接
            return indicators.flatMap((indicator, index) => 
              index === 0 
                ? [indicator] 
                : [<IndicatorSeparator key={`sep-${index}`} />, indicator]
            );
          })()}
        </div>
```

**Step 3: 验证组件语法正确**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无错误输出

---

## Task 6: 端到端验证

**Step 1: 重启服务**

Run: `./manage.sh restart`
Expected: 服务正常启动

**Step 2: 检查后端日志**

Run: `sleep 5 && tail -20 backend/uvicorn.log`
Expected: 无错误，watchlist 接口返回 200

**Step 3: 手动验证**

在浏览器中访问 http://localhost:3000，检查：
- [ ] 温度指标正常显示（如 🔥 温度75）
- [ ] 波动率指标正常显示（如 波动 0.065）
- [ ] 回撤指标正常显示（如 -10.5%，绿色）
- [ ] 分隔符正确显示（淡色圆点）
- [ ] 窄屏时自动换行
- [ ] 趋势指标在 >=2 周时显示

---

## Task 7: 提交代码

**Step 1: 检查变更**

Run: `git diff --stat`
Expected: 只有 `frontend/components/SortableWatchlistItem.tsx` 被修改

**Step 2: 提交**

```bash
git add frontend/components/SortableWatchlistItem.tsx
git commit -m "feat(ui): display all indicators in watchlist cards

- Add VolatilityIndicator component for ATR display
- Add DrawdownIndicator component for drawdown display  
- Add IndicatorSeparator component for visual separation
- Refactor indicators row to show all metrics in compact layout
- Use flex-wrap for responsive narrow screen support"
```

---

## 回滚方案

如果需要回滚，执行：
```bash
git checkout HEAD~1 -- frontend/components/SortableWatchlistItem.tsx
```
