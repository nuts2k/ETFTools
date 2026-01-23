"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Star, Edit3, Check, Search, X } from "lucide-react";
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

export default function WatchlistPage() {
  const { watchlist, isLoaded, add, remove, reorder, isWatched } = useWatchlist();
  const [isEditing, setIsEditing] = useState(false);
  
  // Search state
  const [isSearchMode, setIsSearchMode] = useState(false);
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
    <div className="flex flex-col min-h-[100dvh] bg-background pb-20">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-background/95 backdrop-blur-md pt-safe border-b border-border/50 transform-gpu backface-hidden">
        <div className="flex h-14 items-center justify-between px-5">
          {isSearchMode ? (
            <div className="flex flex-1 items-center gap-2 animate-in fade-in slide-in-from-right-4 duration-200">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <input
                  autoFocus
                  type="text"
                  placeholder="搜索代码或名称"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full h-9 pl-9 pr-4 rounded-full bg-secondary text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                />
                {searchQuery && (
                  <button 
                    onClick={() => setSearchQuery("")}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
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
                className="text-sm font-medium text-primary whitespace-nowrap px-1"
              >
                取消
              </button>
            </div>
          ) : (
            <>
              <h1 className="text-2xl font-bold tracking-tight">自选</h1>
              <div className="flex items-center gap-1 -mr-2">
                <button
                  onClick={() => setIsSearchMode(true)}
                  className="flex items-center justify-center h-10 w-10 rounded-full text-muted-foreground hover:bg-secondary transition-colors"
                >
                  <Search className="h-6 w-6" />
                </button>
                <button 
                  onClick={() => setIsEditing(!isEditing)}
                  className={cn(
                      "flex items-center justify-center h-10 px-3 rounded-full transition-colors text-sm font-medium",
                      isEditing ? "text-primary bg-primary/10" : "text-muted-foreground hover:bg-secondary"
                  )}
                >
                  {isEditing ? (
                      <>
                          <Check className="h-4 w-4 mr-1" />
                          完成
                      </>
                  ) : (
                      <Edit3 className="h-6 w-6" />
                  )}
                </button>
              </div>
            </>
          )}
        </div>
      </header>

      {/* Search Results Layer */}
      {isSearchMode && (
        <div className="flex-1 bg-background px-5 py-4 animate-in fade-in duration-200">
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
          {/* List Header */}
          <div className="px-6 py-2 flex items-center text-xs text-muted-foreground border-b border-border/50 mt-1">
        <div className={cn("flex-1 transition-all", isEditing && "pl-8")}>名称代码</div>
        {!isEditing && (
            <>
                <div className="w-20 text-right pr-2">最新价</div>
                <div className="w-20 text-right">涨跌幅</div>
            </>
        )}
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
                {!isEditing && (
                    <button 
                      onClick={() => setIsSearchMode(true)} 
                      className="mt-4 px-4 py-2 bg-primary text-primary-foreground rounded-full text-sm font-medium hover:bg-primary/90 transition-colors"
                    >
                    去搜索添加
                    </button>
                )}
              </div>
            ) : (
              <div className="flex flex-col pb-safe">
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
