"use client";

import { useState, useEffect, useRef, useMemo } from "react";
import { Search as SearchIcon } from "lucide-react";
import { useDebounce } from "@/hooks/use-debounce";
import { fetchClient, type ETFItem } from "@/lib/api";
import { StockCard } from "@/components/StockCard";
import { useWatchlist } from "@/hooks/use-watchlist";
import { cn } from "@/lib/utils";
import { TAG_COLORS } from "@/lib/tag-colors";

// 搜索页标签按钮专用 ring 边框（不影响 StockCard/详情页的只读标签）
const TAG_RING: Record<string, string> = {
  type: "ring-1 ring-blue-500/20 dark:ring-blue-400/20",
  industry: "ring-1 ring-purple-500/20 dark:ring-purple-400/20",
  strategy: "ring-1 ring-amber-500/20 dark:ring-amber-400/20",
  special: "ring-1 ring-border/50",
};

// 标签 group 对应的圆点颜色（结果标题色彩呼应用）
const GROUP_DOT: Record<string, string> = {
  type: "bg-blue-500",
  industry: "bg-purple-500",
  strategy: "bg-amber-500",
};

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

  // 标签 label → group 的快速查找表，避免渲染路径中 .find() 线性扫描
  const tagGroupMap = useMemo(
    () => Object.fromEntries(popularTags.map(t => [t.label, t.group])),
    [popularTags]
  );

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
    return () => { abortRef.current?.abort(); };
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
              id="search-input"
              name="search"
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
      {popularTags.length > 0 && (
        <div className={cn(
          "relative border-b border-border/30",
          query !== "" && "hidden"
        )}>
          <div
            role="radiogroup"
            aria-label="按标签筛选 ETF"
            className="flex gap-2.5 overflow-x-auto no-scrollbar px-4 py-3 animate-in fade-in slide-in-from-top-1 duration-200"
          >
            {popularTags.map((tag) => (
              <button
                key={tag.label}
                role="radio"
                aria-checked={selectedTag === tag.label}
                onClick={() => handleTagClick(tag.label)}
                className={cn(
                  "shrink-0 rounded-full text-xs font-medium transition-all duration-200 min-h-[44px] active:scale-95",
                  selectedTag === tag.label
                    ? "bg-primary text-primary-foreground shadow-sm shadow-primary/25 ring-0 px-4 py-2"
                    : cn(
                        TAG_COLORS[tag.group] || TAG_COLORS.special,
                        TAG_RING[tag.group] || TAG_RING.special,
                        "px-3.5 py-2"
                      )
                )}
              >
                {tag.label}
              </button>
            ))}
          </div>
          <div
            className="pointer-events-none absolute right-0 top-0 bottom-0 w-8 bg-gradient-to-l from-background to-transparent"
            aria-hidden="true"
          />
        </div>
      )}

      {/* Results Section */}
      <section className={cn(
        "flex flex-col flex-1 px-4 pt-4",
        isSearchActive && "min-h-0 overflow-y-auto pb-20"
      )}>
        {(query || selectedTag) && (
            <div className="flex items-center justify-between pb-3 pt-1">
                <div className="flex items-center gap-2">
                    {selectedTag && (
                      <div className={cn(
                        "h-2 w-2 rounded-full shrink-0",
                        GROUP_DOT[tagGroupMap[selectedTag] ?? ""] || "bg-muted-foreground"
                      )} />
                    )}
                    <h3 className="text-lg font-bold leading-tight tracking-tight">
                        {selectedTag ? `「${selectedTag}」相关` : "搜索结果"}
                    </h3>
                </div>
                <div className="flex items-center gap-2">
                    {selectedTag && !loading && results.length > 0 && (
                        <span className="text-xs text-muted-foreground">{results.length} 只</span>
                    )}
                    <span className="inline-flex items-center rounded bg-primary/10 px-2 py-1 text-[10px] font-medium text-primary ring-1 ring-inset ring-primary/20">
                        QFQ
                    </span>
                </div>
            </div>
        )}

        <div className="flex flex-col gap-3 pb-safe">
            {loading && (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="flex items-center gap-3 rounded-2xl bg-card p-4 shadow-sm">
                    <div className="h-10 w-10 rounded-full bg-secondary animate-pulse shrink-0" />
                    <div className="flex-1 space-y-2">
                      <div className="h-4 bg-secondary animate-pulse rounded-md w-24" />
                      <div className="flex gap-2">
                        <div className="h-3 bg-secondary animate-pulse rounded w-14" />
                        <div className="h-3 bg-secondary animate-pulse rounded w-10" />
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-2 shrink-0">
                      <div className="h-5 bg-secondary animate-pulse rounded-md w-16" />
                      <div className="h-6 bg-secondary animate-pulse rounded-lg w-[72px]" />
                    </div>
                  </div>
                ))}
              </div>
            )}

            {!loading && (query || selectedTag) && results.length === 0 && (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <div className="flex items-center justify-center h-14 w-14 rounded-2xl bg-secondary/50 text-muted-foreground/30 mb-4">
                  <SearchIcon className="h-7 w-7" />
                </div>
                <p className="text-sm text-muted-foreground">
                  {selectedTag ? `暂无「${selectedTag}」相关的 ETF` : "未找到相关结果"}
                </p>
                <p className="text-xs text-muted-foreground/60 mt-1">
                  {selectedTag ? "试试其他标签" : "换个关键词试试"}
                </p>
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
