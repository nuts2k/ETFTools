"use client";

import { RefreshCw, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import type { PullState } from "@/hooks/use-pull-to-refresh";

interface PullToRefreshIndicatorProps {
  pullDistance: number;
  state: PullState;
  threshold: number;
}

export function PullToRefreshIndicator({
  pullDistance,
  state,
  threshold,
}: PullToRefreshIndicatorProps) {
  const progress = Math.min(pullDistance / threshold, 1);
  const rotation = progress * 180;

  const isIdle = state === "idle";
  const isReleased = state === "refreshing" || state === "complete" || isIdle;

  // refreshing/complete 使用固定高度，避免 pullDistance=0 时不可见
  const displayHeight = isIdle
    ? 0
    : state === "refreshing" || state === "complete"
      ? 48
      : pullDistance;

  return (
    <div
      className={cn(
        "overflow-hidden",
        isReleased && "transition-all duration-300"
      )}
      style={{
        height: displayHeight,
        opacity: isIdle ? 0 : 1,
      }}
    >
      <div className="flex items-center justify-center gap-2 h-full">
        {state === "complete" ? (
          <>
            <Check className="h-4 w-4 text-primary" />
            <span className="text-xs text-primary">刷新完成</span>
          </>
        ) : state === "refreshing" ? (
          <>
            <RefreshCw className="h-4 w-4 text-primary animate-spin" />
            <span className="text-xs text-primary">正在刷新...</span>
          </>
        ) : state === "threshold" ? (
          <>
            <RefreshCw
              className="h-4 w-4 text-primary"
              style={{ transform: "rotate(180deg)" }}
            />
            <span className="text-xs text-primary">释放刷新</span>
          </>
        ) : state === "pulling" ? (
          <>
            <RefreshCw
              className="h-4 w-4 text-muted-foreground"
              style={{ transform: `rotate(${rotation}deg)` }}
            />
            <span className="text-xs text-muted-foreground">下拉刷新</span>
          </>
        ) : null}
      </div>
    </div>
  );
}
