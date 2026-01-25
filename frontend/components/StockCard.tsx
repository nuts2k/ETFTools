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
  const badgeColor = isUp ? "bg-up" : isDown ? "bg-down" : "bg-muted";
  const market = etf.code.startsWith("5") ? "SH" : "SZ";

  return (
    <div className="group flex items-center justify-between gap-3 rounded-2xl bg-card p-4 shadow-sm border border-border/40 hover:border-border/80 transition-all">
      <Link href={`/etf/${etf.code}`} className="flex items-center gap-3 flex-1 min-w-0 transition-transform active:scale-[0.98]">
        <div className="relative flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-secondary/50 text-muted-foreground/50 border border-border/50 group-hover:bg-secondary transition-colors">
          <LineChart className="h-6 w-6" />
        </div>
        <div className="flex flex-col justify-center min-w-0 gap-1">
          <p className="text-base font-bold leading-none truncate text-foreground">
            {etf.name}
          </p>
          <div className="flex items-center gap-2">
            <span className="bg-secondary/80 text-muted-foreground text-[10px] font-bold px-1.5 py-0.5 rounded border border-border/30 font-mono">
              {etf.code}
            </span>
            <span className="text-[10px] font-medium text-muted-foreground/60 uppercase tracking-wider">{market} ETF</span>
          </div>
        </div>
      </Link>

      <div className="flex items-center gap-4 shrink-0">
        <div className="flex flex-col items-end gap-1">
          <p className="text-base font-bold tabular-nums text-foreground tracking-tight">
            {etf.price?.toFixed(3)}
          </p>
          <div className={cn(
            "min-w-[56px] flex items-center justify-center rounded-md h-5 px-1.5 text-white text-[10px] font-bold",
            badgeColor
          )}>
            {isUp ? "+" : ""}{etf.change_pct}%
          </div>
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
                    "relative z-30 flex items-center justify-center h-9 w-9 rounded-xl transition-all active:scale-90",
                    isWatched 
                        ? "bg-secondary text-muted-foreground/50" 
                        : "bg-primary text-primary-foreground shadow-md shadow-primary/10 hover:shadow-lg hover:shadow-primary/20"
                )}
            >
                {isWatched ? <Check className="h-4 w-4" /> : <Plus className="h-5 w-5" />}
            </button>
        )}
      </div>
    </div>
  );
}
