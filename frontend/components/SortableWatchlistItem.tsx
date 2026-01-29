import React from "react";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useRouter } from "next/navigation";
import { Trash2, GripVertical } from "lucide-react";
import { cn } from "@/lib/utils";
import { type ETFItem } from "@/lib/api";
import { useLongPress } from "@/hooks/use-long-press";

// 温度等级图标映射
const TEMPERATURE_ICONS: Record<string, string> = {
  freezing: "❄️",
  cool: "🌤️",
  warm: "🌡️",
  hot: "🔥",
};

// 周趋势方向图标
const TREND_ICONS: Record<string, string> = {
  up: "↗️",
  down: "↘️",
  flat: "→",
};

// 趋势指示器组件
function TrendIndicator({ 
  direction, 
  weeks 
}: { 
  direction?: "up" | "down" | "flat" | null; 
  weeks?: number | null;
}) {
  if (!direction || weeks === null || weeks === undefined) {
    return null;
  }
  
  const icon = TREND_ICONS[direction] || "→";
  const absWeeks = Math.abs(weeks);
  
  // 只显示连续2周以上的趋势
  if (absWeeks < 2) {
    return null;
  }
  
  const label = direction === "up" 
    ? `连涨${absWeeks}周` 
    : direction === "down" 
      ? `连跌${absWeeks}周` 
      : null;
  
  if (!label) return null;
  
  return (
    <span className={cn(
      "inline-flex items-center gap-0.5 text-[10px] font-medium",
      direction === "up" ? "text-up" : direction === "down" ? "text-down" : "text-muted-foreground"
    )}>
      <span>{icon}</span>
      <span>{label}</span>
    </span>
  );
}

// 温度指示器组件
function TemperatureIndicator({ 
  score, 
  level 
}: { 
  score?: number | null; 
  level?: "freezing" | "cool" | "warm" | "hot" | null;
}) {
  if (score === null || score === undefined || !level) {
    return null;
  }
  
  const icon = TEMPERATURE_ICONS[level] || "🌤️";
  
  return (
    <span className={cn(
      "inline-flex items-center gap-0.5 text-[10px] font-medium",
      level === "hot" ? "text-up" : 
      level === "warm" ? "text-orange-500" : 
      level === "cool" ? "text-blue-400" : 
      "text-blue-500"
    )}>
      <span>{icon}</span>
      <span className="tabular-nums">温度{Math.round(score)}</span>
    </span>
  );
}

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

// 指标分隔符
function IndicatorSeparator() {
  return <span className="text-muted-foreground/30 text-[10px]">·</span>;
}

// 辅助函数：检查指标是否有值
function hasValue(value: number | null | undefined): boolean {
  return value !== null && value !== undefined;
}

interface Props {
  etf: ETFItem;
  isEditing: boolean;
  onRemove: (code: string) => void;
  onLongPress?: () => void;
}

export function SortableWatchlistItem({ etf, isEditing, onRemove, onLongPress }: Props) {
  const router = useRouter();
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: etf.code, disabled: !isEditing });

  const style = {
    transform: CSS.Translate.toString(transform),
    transition,
    zIndex: isDragging ? 10 : 1,
    position: "relative" as const,
  };

  const isUp = etf.change_pct > 0;
  const isDown = etf.change_pct < 0;
  const badgeColor = isUp ? "bg-up/10 text-up" : isDown ? "bg-down/10 text-down" : "bg-muted text-muted-foreground";

  // Long press handler for non-editing mode
  const longPressHandlers = useLongPress(
    () => {
        if (!isEditing && onLongPress) {
            onLongPress();
        }
    },
    () => {
        // Normal click behavior - navigate
        router.push(`/etf/${etf.code}`);
    },
    { delay: 500 }
  );

  const content = (
    <>
      <div className="flex flex-col flex-1 min-w-0 pr-4">
        <h3 className="text-base font-semibold truncate">{etf.name}</h3>
        <div className="flex items-center gap-2 mt-1">
          <span className="inline-flex items-center justify-center rounded px-1 py-0.5 text-[10px] font-medium bg-secondary text-muted-foreground border border-border/50">
            {etf.code.startsWith("5") ? "SH" : "SZ"}
          </span>
          <span className="text-sm text-muted-foreground font-mono tracking-wide">{etf.code}</span>
        </div>
        
        {/* Compact Indicators Row */}
        <div className="flex items-center gap-1.5 mt-2 flex-wrap text-[10px]">
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
      </div>
      
      {!isEditing ? (
        <div className="flex flex-col items-center justify-center gap-1 min-w-[84px] shrink-0">
          <span className="text-[17px] font-bold tabular-nums tracking-tight text-foreground">
            {etf.price?.toFixed(3)}
          </span>
          <div className={cn(
              "w-[72px] flex items-center justify-center rounded-lg h-[26px] text-[13px] font-bold tabular-nums transition-colors",
              badgeColor
          )}>
            {isUp ? "+" : ""}{etf.change_pct}%
          </div>
        </div>
      ) : (
        <div className="flex items-center justify-center w-10 text-muted-foreground/40 hover:text-muted-foreground transition-colors">
            <GripVertical className="h-5 w-5" />
        </div>
      )}
    </>
  );

  if (isEditing) {
    return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className={cn(
        "group flex items-center justify-between p-4 rounded-2xl bg-card shadow-sm transition-all touch-none select-none",
        isDragging ? "shadow-xl scale-[1.02] z-50 ring-1 ring-border/50 bg-card/95 backdrop-blur-sm" : ""
      )}
    >
      <div 
          className="mr-3 text-red-500/80 cursor-pointer active:scale-90 transition-all p-2 -ml-2 rounded-full hover:bg-red-500/10"
          onClick={(e) => {
              e.stopPropagation(); 
              onRemove(etf.code);
          }}
      >
          <Trash2 className="h-5 w-5" />
      </div>
      {content}
    </div>
  );
}

// Non-editing mode with long press support
return (
  <div 
    {...longPressHandlers}
    className="group flex items-center justify-between p-4 rounded-2xl bg-card shadow-sm active:scale-[0.98] active:shadow-none transition-all cursor-pointer select-none mb-0"
  >
    {content}
  </div>
);
}

