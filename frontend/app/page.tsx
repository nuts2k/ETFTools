"use client";

import { useState } from "react";
import Link from "next/link";
import { Star, Edit3, Check } from "lucide-react";
import { useWatchlist } from "@/hooks/use-watchlist";
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
  const { watchlist, isLoaded, remove, reorder } = useWatchlist();
  const [isEditing, setIsEditing] = useState(false);

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
    <div className="flex flex-col min-h-screen bg-background pb-20">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-background/95 backdrop-blur-md pt-safe border-b border-border/50">
        <div className="flex h-14 items-center justify-between px-5">
          <h1 className="text-2xl font-bold tracking-tight">自选</h1>
          <button 
            onClick={() => setIsEditing(!isEditing)}
            className={cn(
                "flex items-center justify-center h-10 px-3 rounded-full transition-colors -mr-2 text-sm font-medium",
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
      </header>

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
                <Link href="/search" className="mt-4 px-4 py-2 bg-primary text-primary-foreground rounded-full text-sm font-medium hover:bg-primary/90 transition-colors">
                去搜索添加
                </Link>
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
    </div>
  );
}
