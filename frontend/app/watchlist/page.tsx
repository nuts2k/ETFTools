"use client";

import Link from "next/link";
import { Star } from "lucide-react";
import { useWatchlist } from "@/hooks/use-watchlist";
import { cn } from "@/lib/utils";

export default function WatchlistPage() {
  const { watchlist, isLoaded } = useWatchlist();

  return (
    <div className="flex flex-col min-h-screen px-4 py-6 max-w-md mx-auto">
      <div className="sticky top-0 bg-background/95 backdrop-blur z-10 pb-4 pt-2">
        <h1 className="text-2xl font-bold mb-1">自选列表</h1>
        <p className="text-xs text-muted-foreground">你关注的 ETF</p>
      </div>

      <div className="flex-1 mt-2">
        {!isLoaded ? (
          <div className="space-y-3 mt-2">
            {[1, 2, 3].map((i) => (
               <div key={i} className="h-16 bg-secondary/30 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : watchlist.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
            <Star className="h-12 w-12 mb-2 opacity-20" />
            <p className="text-sm">暂无自选 ETF</p>
            <Link href="/" className="mt-4 px-4 py-2 bg-primary text-primary-foreground rounded-full text-sm font-medium">
              去搜索添加
            </Link>
          </div>
        ) : (
          <div className="space-y-3 pb-4">
            {watchlist.map((etf) => (
              <div key={etf.code} className="flex items-center justify-between p-4 bg-card rounded-xl border shadow-sm hover:border-primary/30 transition-colors">
                <Link href={`/etf/${etf.code}`} className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-mono font-bold text-base">{etf.code}</span>
                    <span className="text-xs px-1.5 py-0.5 bg-secondary rounded text-muted-foreground">
                      {etf.code.startsWith("5") ? "SH" : "SZ"}
                    </span>
                  </div>
                  <div className="text-sm text-foreground/90 truncate pr-2">
                    {etf.name}
                  </div>
                </Link>
                
                <div className="flex flex-col items-end gap-1 ml-3 min-w-[80px]">
                  <span className="font-mono text-base font-medium">
                    {etf.price?.toFixed(3)}
                  </span>
                  <span className={cn(
                    "text-xs font-medium px-1.5 py-0.5 rounded",
                    etf.change_pct > 0 ? "text-up bg-up/10" : etf.change_pct < 0 ? "text-down bg-down/10" : "text-muted-foreground bg-muted"
                  )}>
                    {etf.change_pct > 0 ? "+" : ""}{etf.change_pct}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
