"use client";

import { useState, useEffect } from "react";
import { Search } from "lucide-react";
import Link from "next/link";
import { useDebounce } from "@/hooks/use-debounce";
import { fetchClient, type ETFItem } from "@/lib/api";
import { cn } from "@/lib/utils";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ETFItem[]>([]);
  const [loading, setLoading] = useState(false);
  
  // 防抖搜索
  const debouncedQuery = useDebounce(query, 500);

  useEffect(() => {
    async function doSearch() {
      if (!debouncedQuery) {
        setResults([]);
        return;
      }

      setLoading(true);
      try {
        const data = await fetchClient<ETFItem[]>(`/etf/search?q=${encodeURIComponent(debouncedQuery)}`);
        setResults(data);
      } catch (err) {
        console.error("Search failed", err);
      } finally {
        setLoading(false);
      }
    }

    doSearch();
  }, [debouncedQuery]);

  return (
    <div className="flex flex-col min-h-screen px-4 py-6 max-w-md mx-auto">
      {/* Header / Search Bar */}
      <div className="sticky top-0 bg-background/95 backdrop-blur z-10 pb-4 pt-2">
        <h1 className="text-2xl font-bold mb-4">发现 ETF</h1>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input 
            type="text"
            placeholder="输入代码或名称 (如 300, 半导体)"
            className="w-full h-10 pl-9 pr-4 rounded-full border bg-secondary/50 focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all text-sm"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 mt-2">
        {!query && (
          <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
            <Search className="h-12 w-12 mb-2 opacity-20" />
            <p className="text-sm">搜索 ETF (支持代码或名称)</p>
          </div>
        )}

        {loading && (
          <div className="space-y-3 mt-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-16 bg-secondary/30 rounded-lg animate-pulse" />
            ))}
          </div>
        )}

        {!loading && query && results.length === 0 && (
          <div className="text-center py-10 text-muted-foreground">
            未找到相关结果
          </div>
        )}

        <div className="space-y-3 pb-4">
          {results.map((etf) => (
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
      </div>
    </div>
  );
}
