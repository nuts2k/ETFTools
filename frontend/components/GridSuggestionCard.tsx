"use client";

import { Grid3x3, AlertCircle } from "lucide-react";
import type { GridSuggestion } from "@/lib/api";

interface GridSuggestionCardProps {
  gridSuggestion?: GridSuggestion | null;
  isLoading?: boolean;
}

export default function GridSuggestionCard({ gridSuggestion, isLoading }: GridSuggestionCardProps) {
  // Loading 状态
  if (isLoading) {
    return (
      <div className="rounded-lg border bg-card p-4">
        <div className="flex items-center gap-2 mb-3">
          <Grid3x3 className="h-5 w-5 text-muted-foreground" />
          <h3 className="font-semibold">网格交易建议</h3>
        </div>
        <div className="space-y-2">
          <div className="h-4 bg-muted animate-pulse rounded" />
          <div className="h-4 bg-muted animate-pulse rounded w-3/4" />
        </div>
      </div>
    );
  }

  // 无数据状态
  if (!gridSuggestion) {
    return (
      <div className="rounded-lg border bg-card p-4">
        <div className="flex items-center gap-2 mb-3">
          <Grid3x3 className="h-5 w-5 text-muted-foreground" />
          <h3 className="font-semibold">网格交易建议</h3>
        </div>
        <p className="text-sm text-muted-foreground">暂无数据</p>
      </div>
    );
  }

  const { upper, lower, spacing_pct, grid_count, range_start, range_end, is_out_of_range } = gridSuggestion;

  // 正常显示
  return (
    <div className="rounded-lg border bg-card p-4">
      {/* 标题 */}
      <div className="flex items-center gap-2 mb-4">
        <Grid3x3 className="h-5 w-5 text-blue-500" />
        <h3 className="font-semibold">网格交易建议</h3>
      </div>

      {/* 价格区间超出警告 */}
      {is_out_of_range && (
        <div className="mb-3 p-2 rounded bg-yellow-50 dark:bg-yellow-950/20 border border-yellow-200 dark:border-yellow-800">
          <div className="flex items-start gap-2">
            <AlertCircle className="h-4 w-4 text-yellow-600 dark:text-yellow-500 mt-0.5 flex-shrink-0" />
            <p className="text-xs text-yellow-700 dark:text-yellow-400">
              当前价格已超出建议区间 ±5%，建议谨慎操作
            </p>
          </div>
        </div>
      )}

      {/* 网格参数 */}
      <div className="space-y-3">
        {/* 价格区间 */}
        <div className="grid grid-cols-2 gap-3">
          <div className="p-3 rounded-lg bg-blue-50 dark:bg-blue-950/20">
            <div className="text-xs text-muted-foreground mb-1">上界</div>
            <div className="text-lg font-semibold text-blue-600 dark:text-blue-400">
              ¥{upper.toFixed(3)}
            </div>
          </div>
          <div className="p-3 rounded-lg bg-blue-50 dark:bg-blue-950/20">
            <div className="text-xs text-muted-foreground mb-1">下界</div>
            <div className="text-lg font-semibold text-blue-600 dark:text-blue-400">
              ¥{lower.toFixed(3)}
            </div>
          </div>
        </div>

        {/* 网格配置 */}
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div className="flex justify-between">
            <span className="text-muted-foreground">网格间距</span>
            <span className="font-medium">{spacing_pct.toFixed(2)}%</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">网格数量</span>
            <span className="font-medium">{grid_count} 档</span>
          </div>
        </div>

        {/* 分析区间 */}
        <div className="pt-2 border-t text-xs text-muted-foreground">
          <div className="flex items-center justify-between">
            <span>分析区间</span>
            <span>{range_start} ~ {range_end}</span>
          </div>
        </div>

        {/* 说明文字 */}
        <div className="pt-2 text-xs text-muted-foreground">
          <p>💡 基于近 60 天历史波动率（ATR）计算，适合震荡行情</p>
        </div>
      </div>
    </div>
  );
}
