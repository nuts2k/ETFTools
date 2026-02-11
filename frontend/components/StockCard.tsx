"use client";

import Link from "next/link";
import { LineChart, Plus, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ETFItem } from "@/lib/api";

interface StockCardProps {
  etf: ETFItem;
  isWatched?: boolean;
  onToggleWatchlist?: (e: React.MouseEvent) => void;
  searchQuery?: string;
  showTags?: boolean;
}

const TAG_COLORS: Record<string, string> = {
  type: "bg-blue-500/10 text-blue-600 dark:text-blue-400",
  industry: "bg-purple-500/10 text-purple-600 dark:text-purple-400",
  strategy: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
  special: "bg-secondary text-muted-foreground",
};

function HighlightText({ text, highlight }: { text: string; highlight?: string }) {
    if (!highlight || !text) return <>{text}</>;
    
    // Escape special regex characters
    const escapedHighlight = highlight.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const parts = text.split(new RegExp(`(${escapedHighlight})`, 'gi'));
    
    return (
      <>
        {parts.map((part, i) => 
          part.toLowerCase() === highlight.toLowerCase() ? (
            <span key={i} className="text-primary">{part}</span>
          ) : (
            part
          )
        )}
      </>
    );
}

export function StockCard({ etf, isWatched, onToggleWatchlist, searchQuery, showTags = false }: StockCardProps) {
  const isUp = etf.change_pct > 0;
  const isDown = etf.change_pct < 0;
  const badgeColor = isUp ? "bg-up/10 text-up" : isDown ? "bg-down/10 text-down" : "bg-muted text-muted-foreground";
  const market = etf.code.startsWith("5") ? "SH" : "SZ";

  return (
    <div className="group flex items-center justify-between gap-3 rounded-2xl bg-card p-4 shadow-sm transition-all">
      <Link href={`/etf/${etf.code}`} className="flex items-center gap-3 flex-1 min-w-0 transition-transform active:scale-[0.98]">
        <div className="relative flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-full bg-secondary text-foreground/80 font-bold text-sm group-hover:bg-secondary/80 transition-colors">
          {etf.name.charAt(0)}
        </div>
        <div className="flex flex-col justify-center min-w-0 gap-1">
          <p className="text-base font-bold leading-none truncate text-foreground">
            <HighlightText text={etf.name} highlight={searchQuery} />
          </p>
          <div className="flex items-center gap-2 overflow-hidden">
            <span className="bg-secondary/80 text-muted-foreground text-[10px] font-bold px-1.5 py-0.5 rounded border border-border/30 font-mono shrink-0">
              <HighlightText text={etf.code} highlight={searchQuery} />
            </span>
            <span className="text-[10px] font-medium text-muted-foreground/60 uppercase tracking-wider shrink-0">{market} ETF</span>
            {showTags && etf.tags && etf.tags.length > 0 && etf.tags.slice(0, 2).map((tag) => (
              <span
                key={`${tag.group}-${tag.label}`}
                className={cn(
                  "text-[10px] font-medium px-1.5 py-0.5 rounded shrink-0",
                  TAG_COLORS[tag.group] || TAG_COLORS.special
                )}
              >
                {tag.label}
              </span>
            ))}
          </div>
        </div>
      </Link>

      <div className="flex items-center gap-3 shrink-0">
        <div className="flex flex-col items-center justify-center gap-1 min-w-[84px]">
          <p className="text-[17px] font-bold tabular-nums text-foreground tracking-tight leading-none">
            {etf.price?.toFixed(3)}
          </p>
          <div className={cn(
            "w-[72px] flex items-center justify-center rounded-lg h-[26px] text-[13px] font-bold tabular-nums transition-colors",
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
                    "relative flex items-center justify-center h-9 w-9 rounded-xl transition-all active:scale-90",
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
