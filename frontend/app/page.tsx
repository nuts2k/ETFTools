"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { Star, Edit3, Check, Search, X, RefreshCw, ArrowRight, MousePointer2 } from "lucide-react";
import { useWatchlist } from "@/hooks/use-watchlist";
import { useDebounce } from "@/hooks/use-debounce";
import { fetchClient, type ETFItem } from "@/lib/api";
import { StockCard } from "@/components/StockCard";
import { cn } from "@/lib/utils";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
  DragStartEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { SortableWatchlistItem } from "@/components/SortableWatchlistItem";
import { usePullToRefresh } from "@/hooks/use-pull-to-refresh";
import { PullToRefreshIndicator } from "@/components/PullToRefreshIndicator";

export default function WatchlistPage() {
  const { watchlist, isLoaded, add, remove, reorder, isWatched, refresh } = useWatchlist();
  const [isEditing, setIsEditing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  useEffect(() => {
    if (isLoaded && watchlist.length > 0) {
      setLastUpdated(new Date());
    }
  }, [isLoaded, watchlist.length]);

  // Search state
  const [isSearchMode, setIsSearchMode] = useState(false);

  // Pull to refresh
  const scrollRef = useRef<HTMLDivElement>(null);
  const { pullDistance, state: pullState } = usePullToRefresh({
    scrollRef,
    onRefresh: async () => {
      await refresh();
      setLastUpdated(new Date());
    },
    disabled: isSearchMode || isEditing,
  });
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<ETFItem[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const debouncedQuery = useDebounce(searchQuery, 300);

  // Search effect
  useEffect(() => {
    async function doSearch() {
      if (!debouncedQuery) {
        setSearchResults([]);
        return;
      }

      setIsSearching(true);
      try {
        const data = await fetchClient<ETFItem[]>(`/etf/search?q=${encodeURIComponent(debouncedQuery)}`);
        setSearchResults(data);
      } catch (err) {
        console.error("Search failed", err);
      } finally {
        setIsSearching(false);
      }
    }

    if (isSearchMode) {
      doSearch();
    }
  }, [debouncedQuery, isSearchMode]);

  const handleToggleWatchlist = async (e: React.MouseEvent, etf: ETFItem) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (isWatched(etf.code)) {
      remove(etf.code);
    } else {
      // Execute add logic without awaiting to prevent UI blocking
      add(etf);
      
      // Close search mode immediately
      setIsSearchMode(false);
      setSearchQuery("");
      setSearchResults([]);
    }
  };

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        delay: 250, // Long press 250ms to activate drag
        tolerance: 5,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleDragStart = () => {
    // Haptic feedback on drag start
    if (typeof navigator !== "undefined" && navigator.vibrate) {
      navigator.vibrate(10);
    }
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;

    if (over && active.id !== over.id) {
      const oldIndex = watchlist.findIndex((item) => item.code === active.id);
      const newIndex = watchlist.findIndex((item) => item.code === over.id);
      
      const newOrder = arrayMove(watchlist, oldIndex, newIndex);
      reorder(newOrder.map(item => item.code));
    }
  };

  return (
    <div ref={scrollRef} className={cn(
      "bg-background",
      isSearchMode ? "fixed inset-0 z-10 h-[100dvh] flex flex-col overflow-hidden" : "min-h-[100dvh] pb-20"
    )}>
      {/* Header */}
      <header className={cn(
        "z-10 bg-background/80 backdrop-blur-xl pt-safe border-b border-border/40",
        isSearchMode ? "shrink-0" : "sticky top-0"
      )}>
        <div className="flex h-14 items-center justify-between px-4 gap-3">
          {isSearchMode ? (
            <div className="flex flex-1 items-center gap-2 animate-in fade-in slide-in-from-right-2 duration-200">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <input
                  autoFocus
                  type="text"
                  placeholder="搜索代码或名称"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full h-9 pl-9 pr-4 rounded-xl bg-secondary text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                />
                {searchQuery && (
                  <button 
                    onClick={() => setSearchQuery("")}
                    className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-muted-foreground hover:text-foreground rounded-full hover:bg-background/50"
                  >
                    <X className="h-3 w-3" />
                  </button>
                )}
              </div>
              <button 
                onClick={() => {
                  setIsSearchMode(false);
                  setSearchQuery("");
                  setSearchResults([]);
                }}
                className="text-sm font-medium text-primary whitespace-nowrap px-2"
              >
                取消
              </button>
            </div>
          ) : (
            <>
              <h1 className="text-xl font-bold tracking-tight shrink-0">自选</h1>
              
              <button
                onClick={() => setIsSearchMode(true)}
                className="flex-1 flex items-center gap-2 h-9 px-3 rounded-xl bg-secondary/50 text-muted-foreground transition-all hover:bg-secondary active:scale-[0.98]"
              >
                <Search className="h-4 w-4 opacity-50" />
                <span className="text-sm opacity-50 font-medium">搜索代码...</span>
              </button>

              <button 
                onClick={() => setIsEditing(!isEditing)}
                className={cn(
                    "flex items-center justify-center h-9 w-9 rounded-full transition-colors",
                    isEditing ? "text-primary bg-primary/10" : "text-muted-foreground hover:bg-secondary"
                )}
              >
                {isEditing ? (
                    <Check className="h-5 w-5" />
                ) : (
                    <Edit3 className="h-5 w-5" />
                )}
              </button>
            </>
          )}
        </div>
      </header>

      {/* Search Results Layer */}
      {isSearchMode && (
        <div className="flex-1 min-h-0 overflow-y-auto bg-background px-5 py-4 pb-20 animate-in fade-in duration-200">
          <div className="flex flex-col gap-3 pb-safe">
            {isSearching ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-20 bg-secondary/30 rounded-xl animate-pulse" />
                ))}
              </div>
            ) : searchResults.length > 0 ? (
              searchResults.map((etf) => (
                <StockCard 
                  key={etf.code}
                  etf={etf}
                  isWatched={isWatched(etf.code)}
                  onToggleWatchlist={(e) => handleToggleWatchlist(e, etf)}
                  searchQuery={searchQuery}
                />
              ))
            ) : searchQuery ? (
              <div className="text-center py-10 text-muted-foreground">
                未找到相关结果
              </div>
            ) : (
              <div className="text-center py-10 text-muted-foreground text-sm">
                输入代码或名称搜索添加
              </div>
            )}
          </div>
        </div>
      )}

      {/* Main List Content - hidden when searching */}
      {!isSearchMode && (
        <>
          {/* Pull to refresh indicator */}
          <PullToRefreshIndicator
            pullDistance={pullDistance}
            state={pullState}
            threshold={80}
          />

          {/* Status Bar */}
          <div className="flex items-center justify-between px-6 py-2">
            <div className="flex items-center gap-1.5">
              <div className="h-1.5 w-1.5 rounded-full bg-up animate-pulse" />
              <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
                实时行情 {lastUpdated && `· ${lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`}
              </span>
            </div>
            {isEditing && (
              <span className="text-[10px] font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-full animate-in fade-in zoom-in duration-200">
                排序模式
              </span>
            )}
          </div>

          {/* Content */}
          <div className="mt-1">
            {!isLoaded ? (
              <div className="space-y-4 px-5">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="flex items-center justify-between p-4 rounded-2xl bg-card/40 border border-border/40 animate-pulse">
                    <div className="flex-1 space-y-3">
                      <div className="h-4 bg-muted rounded-md w-1/3" />
                      <div className="flex gap-2">
                        <div className="h-3 bg-muted rounded-md w-12" />
                        <div className="h-3 bg-muted rounded-md w-16" />
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-2">
                      <div className="h-5 bg-muted rounded-md w-16" />
                      <div className="h-5 bg-muted rounded-md w-20" />
                    </div>
                  </div>
                ))}
              </div>
            ) : watchlist.length === 0 ? (
              <div className="flex flex-col items-center justify-center min-h-[50vh] px-10 text-center">
                <div className="relative mb-6">
                  <div className="absolute inset-0 bg-primary/5 blur-3xl rounded-full" />
                  <div className="relative flex items-center justify-center h-20 w-20 rounded-3xl bg-secondary/50 text-muted-foreground/30 border border-border/50">
                    <Star className="h-10 w-10" />
                  </div>
                </div>
                <h3 className="text-lg font-bold text-foreground mb-2">开启你的自选列表</h3>
                <p className="text-sm text-muted-foreground mb-8 leading-relaxed">
                  添加你关注的 ETF，实时掌握 QFQ 收益波动、ATR 风险及回撤数据。
                </p>
                {!isEditing && (
                    <button 
                      onClick={() => setIsSearchMode(true)} 
                      className="group flex items-center gap-2 px-6 py-3 bg-primary text-primary-foreground rounded-2xl text-sm font-bold shadow-lg shadow-primary/20 hover:scale-[1.02] active:scale-[0.98] transition-all"
                    >
                      <Search className="h-4 w-4" />
                      立即搜索添加
                      <ArrowRight className="h-4 w-4 opacity-50 group-hover:translate-x-1 transition-transform" />
                    </button>
                )}
              </div>
            ) : (
              <div className="flex flex-col gap-3 px-4 pb-safe">
                <DndContext
                    sensors={sensors}
                    collisionDetection={closestCenter}
                    onDragStart={handleDragStart}
                    onDragEnd={handleDragEnd}
                >
                    <SortableContext 
                        items={watchlist.map(item => item.code)}
                        strategy={verticalListSortingStrategy}
                    >
                        {watchlist.map((etf) => (
                            <SortableWatchlistItem 
                                key={etf.code} 
                                etf={etf} 
                                isEditing={isEditing}
                                onRemove={remove}
                                onLongPress={() => setIsEditing(true)}
                            />
                        ))}
                    </SortableContext>
                </DndContext>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
