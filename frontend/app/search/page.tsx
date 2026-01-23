"use client";

import { useState, useEffect } from "react";
import { Search as SearchIcon } from "lucide-react";
import { useDebounce } from "@/hooks/use-debounce";
import { fetchClient, type ETFItem } from "@/lib/api";
import { StockCard } from "@/components/StockCard";
import { useWatchlist } from "@/hooks/use-watchlist";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ETFItem[]>([]);
  const [loading, setLoading] = useState(false);
  
  const debouncedQuery = useDebounce(query, 500);
  const { isWatched, add, remove } = useWatchlist();

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

  const toggleWatchlist = (e: React.MouseEvent, etf: ETFItem) => {
    e.preventDefault();
    e.stopPropagation();
    if (isWatched(etf.code)) {
        remove(etf.code);
    } else {
        add(etf);
    }
  };

  return (
    <div className="flex flex-col min-h-[100dvh] bg-background pb-20">
      {/* Header */}
      <header className="sticky top-0 z-20 bg-background/95 backdrop-blur-md pt-safe border-b border-border/50 transform-gpu backface-hidden">
        <div className="flex h-14 items-center justify-between px-5">
          <h1 className="text-2xl font-bold tracking-tight">搜索</h1>
        </div>
      </header>

      {/* Search Section */}
      <section className="px-5 py-4">
        <div className="relative">
          <label className="flex flex-col w-full">
            <div className="relative flex w-full items-center rounded-xl h-12 bg-card shadow-sm border border-border focus-within:border-primary focus-within:ring-1 focus-within:ring-primary transition-all">
              <div className="absolute left-4 flex items-center justify-center text-muted-foreground">
                <SearchIcon className="h-5 w-5" />
              </div>
              <input 
                className="h-full w-full bg-transparent rounded-xl border-none pl-11 pr-4 text-base placeholder:text-muted-foreground focus:ring-0 focus:outline-none" 
                placeholder="输入代码或名称 (如 300)" 
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
          </label>
        </div>
        {!query && (
            <p className="mt-2 text-xs text-muted-foreground px-1">尝试搜索 “沪深300” 或 “半导体”</p>
        )}
      </section>

      {/* Results Section */}
      <section className="flex flex-col flex-1 px-5">
        {query && (
            <div className="flex items-center justify-between pb-3 pt-1">
                <h3 className="text-lg font-bold leading-tight tracking-tight">搜索结果</h3>
                <span className="inline-flex items-center rounded bg-primary/10 px-2 py-1 text-[10px] font-medium text-primary ring-1 ring-inset ring-primary/20">
                    QFQ
                </span>
            </div>
        )}

        <div className="flex flex-col gap-3 pb-safe">
            {loading && (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-20 bg-secondary/30 rounded-xl animate-pulse" />
                ))}
              </div>
            )}

            {!loading && query && results.length === 0 && (
              <div className="text-center py-10 text-muted-foreground">
                未找到相关结果
              </div>
            )}

            {results.map((etf) => (
                <StockCard 
                    key={etf.code}
                    etf={etf}
                    isWatched={isWatched(etf.code)}
                    onToggleWatchlist={(e) => toggleWatchlist(e, etf)}
                />
            ))}
        </div>
      </section>
    </div>
  );
}
