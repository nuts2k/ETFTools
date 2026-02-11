"use client";

import { useState, useEffect, useRef } from "react";
import { Search as SearchIcon } from "lucide-react";
import { useDebounce } from "@/hooks/use-debounce";
import { fetchClient, type ETFItem } from "@/lib/api";
import { StockCard } from "@/components/StockCard";
import { useWatchlist } from "@/hooks/use-watchlist";
import { cn } from "@/lib/utils";
import { TAG_COLORS } from "@/lib/tag-colors";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ETFItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [inputFocused, setInputFocused] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const [selectedTag, setSelectedTag] = useState<string | null>(null);
  const [popularTags, setPopularTags] = useState<Array<{label: string; group: string}>>([]);
  const abortRef = useRef<AbortController | null>(null);

  const debouncedQuery = useDebounce(query, 500);
  const { isWatched, add, remove } = useWatchlist();

  useEffect(() => {
    fetchClient<Array<{label: string; group: string}>>("/etf/tags/popular")
      .then(setPopularTags)
      .catch(() => {});
  }, []);

  useEffect(() => {
    async function doSearch() {
      if (!debouncedQuery && !selectedTag) {
        setResults([]);
        return;
      }

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setLoading(true);
      try {
        const url = selectedTag
          ? `/etf/search?tag=${encodeURIComponent(selectedTag)}`
          : `/etf/search?q=${encodeURIComponent(debouncedQuery)}`;
        const data = await fetchClient<ETFItem[]>(url, { signal: controller.signal });
        setResults(data);
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        console.error("Search failed", err);
      } finally {
        setLoading(false);
      }
    }
    doSearch();
  }, [debouncedQuery, selectedTag]);

  const toggleWatchlist = (e: React.MouseEvent, etf: ETFItem) => {
    e.preventDefault();
    e.stopPropagation();
    if (isWatched(etf.code)) {
        remove(etf.code);
    } else {
        add(etf);
    }
  };

  const handleTagClick = (label: string) => {
    setSelectedTag(prev => prev === label ? null : label);
  };

  const isSearchActive = query.length > 0 || inputFocused || selectedTag !== null;

  return (
    <div className={cn(
      "flex flex-col bg-background",
      isSearchActive ? "fixed inset-0 z-10 h-[100dvh] overflow-hidden" : "min-h-[100dvh] pb-20"
    )}>
      {/* Header with Search */}
      <header className={cn(
        "z-20 bg-background/80 backdrop-blur-xl pt-safe border-b border-border/40",
        isSearchActive ? "shrink-0" : "sticky top-0"
      )}>
        <div className="flex flex-col px-4 pb-3">
          <div className="flex h-12 items-center">
            <h1 className="text-xl font-bold tracking-tight">搜索</h1>
          </div>
          <div className="relative">
            <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input
              ref={inputRef}
              className="w-full h-10 pl-10 pr-4 rounded-xl bg-secondary text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
              placeholder="输入代码或名称 (如 沪深300)"
              type="search"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                if (e.target.value) setSelectedTag(null);
              }}
              onFocus={() => setInputFocused(true)}
              onBlur={() => setInputFocused(false)}
            />
          </div>
        </div>
      </header>

      {/* Tag Filter Row */}
      {query === "" && popularTags.length > 0 && (
        <div
          role="radiogroup"
          aria-label="按标签筛选 ETF"
          className="flex gap-2 overflow-x-auto no-scrollbar px-4 py-3"
        >
          {popularTags.map((tag) => (
            <button
              key={tag.label}
              role="radio"
              aria-checked={selectedTag === tag.label}
              onClick={() => handleTagClick(tag.label)}
              className={cn(
                "shrink-0 px-3 py-1.5 rounded-full text-xs font-medium transition-colors min-h-[36px]",
                selectedTag === tag.label
                  ? "bg-primary text-primary-foreground"
                  : TAG_COLORS[tag.group] || TAG_COLORS.special
              )}
            >
              {tag.label}
            </button>
          ))}
        </div>
      )}

      {/* Results Section */}
      <section className={cn(
        "flex flex-col flex-1 px-4 pt-4",
        isSearchActive && "min-h-0 overflow-y-auto pb-20"
      )}>
        {(query || selectedTag) && (
            <div className="flex items-center justify-between pb-3 pt-1">
                <h3 className="text-lg font-bold leading-tight tracking-tight">
                    {selectedTag ? `「${selectedTag}」相关` : "搜索结果"}
                </h3>
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

            {!loading && (query || selectedTag) && results.length === 0 && (
              <div className="text-center py-10 text-muted-foreground">
                {selectedTag ? `未找到「${selectedTag}」相关的 ETF` : "未找到相关结果"}
              </div>
            )}

            {results.map((etf) => (
                <StockCard
                    key={etf.code}
                    etf={etf}
                    showTags={true}
                    searchQuery={debouncedQuery}
                    isWatched={isWatched(etf.code)}
                    onToggleWatchlist={(e) => toggleWatchlist(e, etf)}
                />
            ))}
        </div>
      </section>
    </div>
  );
}
