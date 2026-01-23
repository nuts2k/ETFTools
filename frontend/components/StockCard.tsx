"use client";

import Link from "next/link";
import { LineChart, Plus, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ETFItem } from "@/lib/api";

interface StockCardProps {
  etf: ETFItem;
  isWatched?: boolean;
  onToggleWatchlist?: (e: React.MouseEvent) => void;
}

export function StockCard({ etf, isWatched, onToggleWatchlist }: StockCardProps) {
  const isUp = etf.change_pct > 0;
  const isDown = etf.change_pct < 0;
  const changeColor = isUp ? "text-up" : isDown ? "text-down" : "text-muted-foreground";
  const market = etf.code.startsWith("5") ? "SH" : "SZ";

  return (
    <div className="group flex items-center justify-between gap-3 rounded-xl bg-card p-4 shadow-sm border border-border/50 hover:border-border transition-all">
      <Link href={`/etf/${etf.code}`} className="flex items-center gap-3 flex-1 min-w-0 transition-transform active:scale-[0.98]">
        <div className="relative flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-secondary text-muted-foreground/70">
          <LineChart className="h-6 w-6" />
        </div>
        <div className="flex flex-col justify-center min-w-0 gap-0.5">
          <p className="text-base font-medium leading-tight truncate text-foreground">
            {etf.name}
          </p>
          <div className="flex items-center gap-2">
            <span className="bg-secondary text-secondary-foreground text-[10px] font-bold px-1.5 py-0.5 rounded">
              {etf.code}
            </span>
            <span className="text-xs text-muted-foreground">ETF • {market}</span>
          </div>
        </div>
      </Link>

      <div className="flex items-center gap-3 shrink-0">
        <div className="flex flex-col items-end">
          <p className="text-base font-bold tabular-nums text-foreground">
            ¥{etf.price?.toFixed(3)}
          </p>
          <p className={cn("text-xs font-semibold tabular-nums flex items-center", changeColor)}>
            {isUp ? "+" : ""}{etf.change_pct}%
          </p>
        </div>
        
        {onToggleWatchlist && (
            <button 
                type="button"
                onPointerDown={(e) => e.stopPropagation()}
                onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    onToggleWatchlist(e);
                }}
                className={cn(
                    "relative z-30 flex items-center justify-center h-8 w-8 rounded-lg transition-all active:scale-95",
                    isWatched 
                        ? "bg-secondary text-muted-foreground" 
                        : "bg-primary/10 text-primary hover:bg-primary/20"
                )}
            >
                {isWatched ? <Check className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
            </button>
        )}
      </div>
    </div>
  );
}
