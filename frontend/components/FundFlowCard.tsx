"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import type { FundFlowData } from "@/lib/api";

interface FundFlowCardProps {
  data: FundFlowData | null;
  isLoading: boolean;
}

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

      {/* 当前规模骨架 */}
      <div className="space-y-2">
        <Skeleton className="h-4 w-16" />
        <Skeleton className="h-8 w-32" />
        <Skeleton className="h-6 w-36" />
      </div>

      <div className="border-t border-border" />

      {/* 规模排名骨架 */}
      <div className="space-y-2">
        <Skeleton className="h-4 w-16" />
        <Skeleton className="h-6 w-28" />
        <Skeleton className="h-4 w-48" />
      </div>

      <div className="border-t border-border mt-4 pt-2" />
      <Skeleton className="h-3 w-40" />
    </div>
  );
}

export default function FundFlowCard({
  data,
  isLoading,
}: FundFlowCardProps) {
  const [tooltipOpen, setTooltipOpen] = useState(false);

  if (isLoading) {
    return <LoadingSkeleton />;
  }

  // 如果没有数据，不渲染
  if (!data) {
    return null;
  }

  const { current_scale, rank } = data;

  return (
    <div className="bg-card rounded-xl p-4 shadow-sm border border-border">
      <div className="flex items-center gap-2 mb-4">
        <h3 className="text-sm font-medium text-muted-foreground">资金流向</h3>
        <div className="relative">
          <svg
            className="w-4 h-4 text-muted-foreground/60 cursor-help"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            onClick={() => setTooltipOpen(!tooltipOpen)}
            onMouseEnter={() => setTooltipOpen(true)}
            onMouseLeave={() => setTooltipOpen(false)}
          >
            <circle cx="12" cy="12" r="10" strokeWidth="2" />
            <path d="M12 16v-4M12 8h.01" strokeWidth="2" strokeLinecap="round" />
          </svg>
          <div className={cn(
            "absolute left-0 top-6 w-64 p-3 bg-popover text-popover-foreground text-xs rounded-lg shadow-lg border border-border transition-all duration-200 z-10",
            tooltipOpen ? "opacity-100 visible" : "opacity-0 invisible"
          )}>
            <p className="font-medium mb-1">份额与规模说明</p>
            <p className="mb-2">
              <strong>份额：</strong>ETF 的总份数（类似股票的总股本）
            </p>
            <p>
              <strong>规模：</strong>份额 × 净值，代表 ETF 的总市值
            </p>
          </div>
        </div>
      </div>

      {/* 当前规模区块 */}
      <div className="space-y-2 mb-4">
        <span className="text-sm text-muted-foreground">当前规模</span>

        {/* 份额 */}
        <div className="text-2xl font-bold tabular-nums">
          {current_scale.shares.toLocaleString()} 亿份
        </div>

        {/* 规模（可能为 null） */}
        {current_scale.scale !== null ? (
          <div className="text-lg text-muted-foreground tabular-nums">
            {current_scale.scale.toLocaleString()} 亿元
          </div>
        ) : (
          <div className="text-lg text-muted-foreground">
            暂无规模数据
          </div>
        )}
      </div>

      {/* 规模排名区块（仅在有排名数据时显示） */}
      {rank && (
        <>
          <div className="border-t border-border my-4" />

          <div className="space-y-2">
            <span className="text-sm text-muted-foreground">规模排名</span>

            {/* 排名 */}
            <div className="text-lg font-medium tabular-nums">
              第 {rank.rank} 名 / {rank.total_count} 只
            </div>

            {/* 百分位 */}
            <div className="text-sm text-muted-foreground">
              超过 {rank.percentile.toFixed(1)}% 的{rank.category}
            </div>
          </div>
        </>
      )}

      {/* Footer: 数据日期 */}
      <div className="border-t border-border mt-4 pt-2">
        <div className="text-[10px] text-muted-foreground/60">
          数据日期: {current_scale.update_date}
        </div>
      </div>
    </div>
  );
}
