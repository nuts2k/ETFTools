"use client";

import Link from "next/link";
import { Star, Edit3 } from "lucide-react";
import { useWatchlist } from "@/hooks/use-watchlist";
import { cn } from "@/lib/utils";

export default function WatchlistPage() {
  const { watchlist, isLoaded } = useWatchlist();

  return (
    <div className="flex flex-col min-h-screen bg-background pb-20">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-background/95 backdrop-blur-md pt-safe border-b border-border/50">
        <div className="flex h-14 items-center justify-between px-5">
          <h1 className="text-2xl font-bold tracking-tight">自选</h1>
          <button className="flex items-center justify-center w-10 h-10 rounded-full hover:bg-secondary transition-colors text-muted-foreground -mr-2">
            <Edit3 className="h-6 w-6" />
          </button>
        </div>
      </header>

      {/* List Header */}
      <div className="px-6 py-2 flex items-center text-xs text-muted-foreground border-b border-border/50 mt-1">
        <div className="flex-1">名称代码</div>
        <div className="w-20 text-right pr-2">最新价</div>
        <div className="w-20 text-right">涨跌幅</div>
      </div>

      {/* Content */}
      <div className="flex-1">
        {!isLoaded ? (
          <div className="space-y-0 mt-0">
            {[1, 2, 3].map((i) => (
               <div key={i} className="h-16 border-b border-border/30 bg-card/50 animate-pulse" />
            ))}
          </div>
        ) : watchlist.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
            <Star className="h-12 w-12 mb-2 opacity-20" />
            <p className="text-sm">暂无自选 ETF</p>
            <Link href="/search" className="mt-4 px-4 py-2 bg-primary text-primary-foreground rounded-full text-sm font-medium hover:bg-primary/90 transition-colors">
              去搜索添加
            </Link>
          </div>
        ) : (
          <div className="flex flex-col pb-safe">
            {watchlist.map((etf) => {
                const isUp = etf.change_pct > 0;
                const isDown = etf.change_pct < 0;
                const changeColor = isUp ? "text-up" : isDown ? "text-down" : "text-muted-foreground";
                const badgeColor = isUp ? "bg-up" : isDown ? "bg-down" : "bg-muted";

                return (
                  <Link 
                    key={etf.code} 
                    href={`/etf/${etf.code}`}
                    className="group flex items-center justify-between px-6 py-4 active:bg-secondary/50 border-b border-border/30 cursor-pointer transition-colors"
                  >
                    <div className="flex flex-col flex-1 min-w-0 pr-4">
                      <h3 className="text-base font-semibold truncate">{etf.name}</h3>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="inline-flex items-center justify-center rounded px-1 py-0.5 text-[10px] font-medium bg-secondary text-muted-foreground border border-border/50">
                            {etf.code.startsWith("5") ? "SH" : "SZ"}
                        </span>
                        <span className="text-sm text-muted-foreground font-mono tracking-wide">{etf.code}</span>
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-4">
                      <span className={cn("text-base font-bold tabular-nums tracking-tight", changeColor)}>
                        {etf.price?.toFixed(3)}
                      </span>
                      <div className={cn(
                          "min-w-[72px] flex items-center justify-center rounded-lg h-8 px-2 text-white text-sm font-bold shadow-sm",
                          badgeColor
                      )}>
                        {isUp ? "+" : ""}{etf.change_pct}%
                      </div>
                    </div>
                  </Link>
                );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
