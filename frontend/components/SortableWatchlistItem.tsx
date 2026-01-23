import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useRouter } from "next/navigation";
import { Trash2, GripVertical } from "lucide-react";
import { cn } from "@/lib/utils";
import { type ETFItem } from "@/lib/api";
import { useLongPress } from "@/hooks/use-long-press";

interface Props {
  etf: ETFItem;
  isEditing: boolean;
  onRemove: (code: string) => void;
  onLongPress?: () => void;
}

export function SortableWatchlistItem({ etf, isEditing, onRemove, onLongPress }: Props) {
  const router = useRouter();
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: etf.code, disabled: !isEditing });

  const style = {
    transform: CSS.Translate.toString(transform),
    transition,
    zIndex: isDragging ? 10 : 1,
    position: "relative" as const,
  };

  const isUp = etf.change_pct > 0;
  const isDown = etf.change_pct < 0;
  const changeColor = isUp ? "text-up" : isDown ? "text-down" : "text-muted-foreground";
  const badgeColor = isUp ? "bg-up" : isDown ? "bg-down" : "bg-muted";

  // Long press handler for non-editing mode
  const longPressHandlers = useLongPress(
    () => {
        if (!isEditing && onLongPress) {
            onLongPress();
        }
    },
    () => {
        // Normal click behavior - navigate
        router.push(`/etf/${etf.code}`);
    },
    { delay: 500 }
  );

  const content = (
    <>
      <div className="flex flex-col flex-1 min-w-0 pr-4">
        <h3 className="text-base font-semibold truncate">{etf.name}</h3>
        <div className="flex items-center gap-2 mt-1">
          <span className="inline-flex items-center justify-center rounded px-1 py-0.5 text-[10px] font-medium bg-secondary text-muted-foreground border border-border/50">
            {etf.code.startsWith("5") ? "SH" : "SZ"}
          </span>
          <span className="text-sm text-muted-foreground font-mono tracking-wide">{etf.code}</span>
        </div>
        
        {/* Dual-line Metrics Display */}
        <div className="flex items-center gap-3 mt-1.5 text-[10px] text-muted-foreground/80 font-medium tracking-tight">
             <div className="flex items-center gap-1">
                <span>ATR:</span>
                <span className="text-foreground/90 tabular-nums">
                    {etf.atr !== undefined && etf.atr !== null ? etf.atr.toFixed(4) : "--"}
                </span>
             </div>
             <div className="w-[1px] h-2.5 bg-border/80" />
             <div className="flex items-center gap-1">
                <span>120日回撤:</span>
                <span className={cn(
                    "tabular-nums", 
                    (etf.current_drawdown || 0) < 0 ? "text-down font-bold" : "text-foreground/90"
                )}>
                    {etf.current_drawdown !== undefined && etf.current_drawdown !== null 
                        ? `${(etf.current_drawdown * 100).toFixed(2)}%` 
                        : "--"}
                </span>
             </div>
        </div>
      </div>
      
      {!isEditing ? (
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
      ) : (
        <div className="flex items-center justify-center w-10 text-muted-foreground/50">
           <GripVertical className="h-6 w-6" />
        </div>
      )}
    </>
  );

  if (isEditing) {
    return (
      <div
        ref={setNodeRef}
        style={style}
        {...attributes}
        {...listeners}
        className={cn(
          "group flex items-center justify-between px-4 py-4 border-b border-border/30 bg-background transition-colors touch-none select-none",
          isDragging && "shadow-lg bg-secondary/50 scale-[1.02]"
        )}
      >
        <div 
            className="mr-4 text-red-500 cursor-pointer active:scale-95 transition-transform"
            onClick={(e) => {
                e.stopPropagation(); // Prevent drag start if clicking remove
                onRemove(etf.code);
            }}
        >
            <Trash2 className="h-5 w-5 fill-none" />
        </div>
        {content}
      </div>
    );
  }

  // Non-editing mode with long press support
  return (
    <div 
      {...longPressHandlers}
      className="group flex items-center justify-between px-6 py-4 active:bg-secondary/50 border-b border-border/30 cursor-pointer transition-colors select-none"
    >
      {content}
    </div>
  );
}
