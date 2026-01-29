"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { cn } from "@/lib/utils";
import type { WeeklyTrend, DailyTrend, Temperature } from "@/lib/api";

interface TrendAnalysisCardProps {
  weeklyTrend?: WeeklyTrend | null;
  dailyTrend?: DailyTrend | null;
  temperature?: Temperature | null;
  isLoading?: boolean;
}

// 周趋势方向图标和文字
function getWeeklyDirectionDisplay(direction: WeeklyTrend["direction"], weeks: number) {
  const absWeeks = Math.abs(weeks);
  switch (direction) {
    case "up":
      return {
        icon: <TrendingUp className="h-4 w-4 text-up" />,
        text: `连续上涨 ${absWeeks} 周`,
        colorClass: "text-up",
      };
    case "down":
      return {
        icon: <TrendingDown className="h-4 w-4 text-down" />,
        text: `连续下跌 ${absWeeks} 周`,
        colorClass: "text-down",
      };
    default:
      return {
        icon: <Minus className="h-4 w-4 text-muted-foreground" />,
        text: "横盘整理",
        colorClass: "text-muted-foreground",
      };
  }
}

// 周均线状态文字
function getMaStatusText(status: WeeklyTrend["ma_status"]) {
  switch (status) {
    case "bullish":
      return { text: "多头排列 (MA5>10>20)", colorClass: "text-up" };
    case "bearish":
      return { text: "空头排列 (MA5<10<20)", colorClass: "text-down" };
    default:
      return { text: "均线交织", colorClass: "text-muted-foreground" };
  }
}

// 日均线位置显示
function getMaPositionDisplay(position: DailyTrend["ma5_position"]) {
  switch (position) {
    case "above":
      return { icon: "●", text: "价格在上方", colorClass: "text-up" };
    case "below":
      return { icon: "○", text: "价格在下方", colorClass: "text-down" };
    case "crossing_up":
      return { icon: "▲", text: "今日向上突破", colorClass: "text-up" };
    case "crossing_down":
      return { icon: "▼", text: "今日向下跌破", colorClass: "text-down" };
    default:
      return { icon: "○", text: "价格在下方", colorClass: "text-muted-foreground" };
  }
}

// 日均线整体排列状态
function getMaAlignmentText(alignment: DailyTrend["ma_alignment"]) {
  switch (alignment) {
    case "bullish":
      return { text: "多头排列", colorClass: "text-up" };
    case "bearish":
      return { text: "空头排列", colorClass: "text-down" };
    default:
      return { text: "震荡整理", colorClass: "text-muted-foreground" };
  }
}

// 温度等级显示
function getTemperatureDisplay(level: Temperature["level"], score: number) {
  switch (level) {
    case "freezing":
      return { emoji: "❄️", text: "极冷区间", colorClass: "text-blue-500", bgClass: "bg-blue-500" };
    case "cool":
      return { emoji: "🌤️", text: "温和区间", colorClass: "text-cyan-500", bgClass: "bg-cyan-500" };
    case "warm":
      return { emoji: "☀️", text: "偏热区间", colorClass: "text-orange-500", bgClass: "bg-orange-500" };
    case "hot":
      return { emoji: "🔥", text: "过热区间", colorClass: "text-red-500", bgClass: "bg-red-500" };
    default:
      return { emoji: "🌤️", text: "温和区间", colorClass: "text-muted-foreground", bgClass: "bg-muted" };
  }
}

// 因子名称映射
const factorNames: Record<string, string> = {
  drawdown_score: "回撤程度",
  rsi_score: "RSI指标",
  percentile_score: "历史分位",
  volatility_score: "波动水平",
  trend_score: "趋势强度",
};

// 骨架屏组件
function Skeleton({ className }: { className?: string }) {
  return (
    <div className={cn("animate-pulse rounded bg-muted", className)} />
  );
}

// 加载状态骨架屏
function LoadingSkeleton() {
  return (
    <div className="bg-card rounded-xl p-4 shadow-sm border border-border space-y-4">
      <Skeleton className="h-5 w-24" />
      
      {/* 周趋势骨架 */}
      <div className="space-y-2">
        <div className="flex justify-between">
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-4 w-28" />
        </div>
        <div className="flex justify-between">
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-4 w-36" />
        </div>
      </div>

      <div className="border-t border-border" />

      {/* 日均线骨架 */}
      <div className="space-y-2">
        <Skeleton className="h-4 w-20" />
        <div className="space-y-1.5">
          {[1, 2, 3].map((i) => (
            <div key={i} className="flex justify-between">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-20" />
            </div>
          ))}
        </div>
      </div>

      <div className="border-t border-border" />

      {/* 温度计骨架 */}
      <div className="space-y-2">
        <div className="flex justify-between">
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-24" />
        </div>
        <Skeleton className="h-2 w-full rounded-full" />
      </div>
    </div>
  );
}

export default function TrendAnalysisCard({
  weeklyTrend,
  dailyTrend,
  temperature,
  isLoading = false,
}: TrendAnalysisCardProps) {
  const [showFactors, setShowFactors] = useState(false);

  if (isLoading) {
    return <LoadingSkeleton />;
  }

  // 如果所有数据都为空，不渲染
  if (!weeklyTrend && !dailyTrend && !temperature) {
    return null;
  }

  return (
    <div className="bg-card rounded-xl p-4 shadow-sm border border-border">
      <h3 className="text-sm font-medium text-muted-foreground mb-4">趋势分析</h3>

      {/* 周趋势区块 */}
      {weeklyTrend && (
        <div className="space-y-2 mb-4">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">周趋势</span>
            <div className="flex items-center gap-1.5">
              {getWeeklyDirectionDisplay(weeklyTrend.direction, weeklyTrend.consecutive_weeks).icon}
              <span className={cn("text-sm font-medium", getWeeklyDirectionDisplay(weeklyTrend.direction, weeklyTrend.consecutive_weeks).colorClass)}>
                {getWeeklyDirectionDisplay(weeklyTrend.direction, weeklyTrend.consecutive_weeks).text}
              </span>
            </div>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">周均线</span>
            <span className={cn("text-sm font-medium", getMaStatusText(weeklyTrend.ma_status).colorClass)}>
              {getMaStatusText(weeklyTrend.ma_status).text}
            </span>
          </div>
        </div>
      )}

      {/* 分隔线 */}
      {weeklyTrend && dailyTrend && <div className="border-t border-border my-4" />}

      {/* 日均线状态区块 */}
      {dailyTrend && (
        <div className="space-y-2 mb-4">
          <span className="text-sm text-muted-foreground">日均线状态</span>
          
          {/* MA5 */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-sm text-foreground">MA5</span>
              <span className="text-xs text-muted-foreground">({dailyTrend.ma_values.ma5.toFixed(2)})</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className={cn("text-sm", getMaPositionDisplay(dailyTrend.ma5_position).colorClass)}>
                {getMaPositionDisplay(dailyTrend.ma5_position).icon}
              </span>
              <span className={cn("text-xs", getMaPositionDisplay(dailyTrend.ma5_position).colorClass)}>
                {getMaPositionDisplay(dailyTrend.ma5_position).text}
              </span>
            </div>
          </div>

          {/* MA20 */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-sm text-foreground">MA20</span>
              <span className="text-xs text-muted-foreground">({dailyTrend.ma_values.ma20.toFixed(2)})</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className={cn("text-sm", getMaPositionDisplay(dailyTrend.ma20_position).colorClass)}>
                {getMaPositionDisplay(dailyTrend.ma20_position).icon}
              </span>
              <span className={cn("text-xs", getMaPositionDisplay(dailyTrend.ma20_position).colorClass)}>
                {getMaPositionDisplay(dailyTrend.ma20_position).text}
              </span>
            </div>
          </div>

          {/* MA60 */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-sm text-foreground">MA60</span>
              <span className="text-xs text-muted-foreground">({dailyTrend.ma_values.ma60.toFixed(2)})</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className={cn("text-sm", getMaPositionDisplay(dailyTrend.ma60_position).colorClass)}>
                {getMaPositionDisplay(dailyTrend.ma60_position).icon}
              </span>
              <span className={cn("text-xs", getMaPositionDisplay(dailyTrend.ma60_position).colorClass)}>
                {getMaPositionDisplay(dailyTrend.ma60_position).text}
              </span>
            </div>
          </div>

          {/* 整体排列 */}
          <div className="flex items-center justify-between pt-1">
            <span className="text-sm text-muted-foreground">整体排列</span>
            <span className={cn("text-sm font-medium", getMaAlignmentText(dailyTrend.ma_alignment).colorClass)}>
              {getMaAlignmentText(dailyTrend.ma_alignment).text}
            </span>
          </div>
        </div>
      )}

      {/* 分隔线 */}
      {(weeklyTrend || dailyTrend) && temperature && <div className="border-t border-border my-4" />}

      {/* 温度计区块 */}
      {temperature && (
        <div className="space-y-3">
          {/* 温度标题行 */}
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">投资温度</span>
            <div className="flex items-center gap-1.5">
              <span>{getTemperatureDisplay(temperature.level, temperature.score).emoji}</span>
              <span className={cn("text-sm font-bold tabular-nums", getTemperatureDisplay(temperature.level, temperature.score).colorClass)}>
                {temperature.score} / 100
              </span>
            </div>
          </div>

          {/* 温度进度条 */}
          <div className="relative">
            <div className="h-2 bg-secondary rounded-full overflow-hidden w-full relative">
              {/* 背景渐变区域 */}
              <div className="absolute left-0 top-0 h-full w-[25%] bg-blue-500/20" />
              <div className="absolute left-[25%] top-0 h-full w-[25%] bg-cyan-500/20" />
              <div className="absolute left-[50%] top-0 h-full w-[25%] bg-orange-500/20" />
              <div className="absolute left-[75%] top-0 h-full w-[25%] bg-red-500/20" />
              
              {/* 进度填充 */}
              <div
                className={cn(
                  "absolute left-0 top-0 h-full transition-all duration-500 rounded-full",
                  getTemperatureDisplay(temperature.level, temperature.score).bgClass
                )}
                style={{ width: `${Math.min(Math.max(temperature.score, 0), 100)}%` }}
              />
            </div>
            <div className="flex justify-between text-[10px] text-muted-foreground mt-1">
              <span>极冷</span>
              <span className={getTemperatureDisplay(temperature.level, temperature.score).colorClass}>
                {getTemperatureDisplay(temperature.level, temperature.score).text}
              </span>
              <span>过热</span>
            </div>
          </div>

          {/* 因子明细折叠区 */}
          <div className="pt-2">
            <button
              type="button"
              onClick={() => setShowFactors(!showFactors)}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              <span>构成因子</span>
              {showFactors ? (
                <ChevronUp className="h-3 w-3" />
              ) : (
                <ChevronDown className="h-3 w-3" />
              )}
            </button>

            {showFactors && (
              <div className="mt-2 space-y-1.5 pl-2 border-l-2 border-border">
                {/* 回撤程度 */}
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">· {factorNames.drawdown_score}</span>
                  <span className="text-foreground tabular-nums">
                    {temperature.factors.drawdown_score}
                  </span>
                </div>

                {/* RSI指标 */}
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">· {factorNames.rsi_score}</span>
                  <span className="text-foreground tabular-nums">
                    {temperature.factors.rsi_score}
                    <span className="text-muted-foreground ml-1">(RSI={temperature.rsi_value.toFixed(0)})</span>
                  </span>
                </div>

                {/* 历史分位 */}
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">· {factorNames.percentile_score}</span>
                  <span className="text-foreground tabular-nums">
                    {temperature.factors.percentile_score}
                    <span className="text-muted-foreground ml-1">
                      (近{temperature.percentile_years}年{temperature.percentile_value.toFixed(0)}%分位)
                    </span>
                  </span>
                </div>

                {/* 波动水平 */}
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">· {factorNames.volatility_score}</span>
                  <span className="text-foreground tabular-nums">
                    {temperature.factors.volatility_score}
                  </span>
                </div>

                {/* 趋势强度 */}
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">· {factorNames.trend_score}</span>
                  <span className="text-foreground tabular-nums">
                    {temperature.factors.trend_score}
                  </span>
                </div>

                {/* 分位数据说明 */}
                {temperature.percentile_note && (
                  <div className="text-[10px] text-muted-foreground/60 pt-1">
                    * {temperature.percentile_note}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
