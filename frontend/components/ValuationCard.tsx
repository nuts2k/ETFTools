"use client";

import { ETFValuation } from "@/lib/api";

interface ValuationCardProps {
  data: ETFValuation;
}

export default function ValuationCard({ data }: ValuationCardProps) {
  const { pe, pe_percentile, dist_view, index_name, history_years, data_date } = data;

  // 颜色逻辑
  let colorClass = "text-yellow-500";
  let bgClass = "bg-yellow-500";
  
  if (dist_view === "低估") {
    colorClass = "text-green-500";
    bgClass = "bg-green-500";
  } else if (dist_view === "高估") {
    colorClass = "text-red-500";
    bgClass = "bg-red-500";
  } else if (dist_view.includes("短期")) {
    colorClass = "text-muted-foreground";
    bgClass = "bg-muted-foreground";
  }

  return (
    <div className="bg-card rounded-xl p-4 shadow-sm border border-border">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="text-sm font-medium text-muted-foreground">估值分析</h3>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-xs px-1.5 py-0.5 rounded bg-secondary text-secondary-foreground">
              {index_name}
            </span>
            <span className="text-xs text-muted-foreground">PE(TTM)</span>
          </div>
        </div>
        <div className={`text-right ${colorClass}`}>
          <div className="text-2xl font-bold">{pe.toFixed(2)}</div>
          <div className="text-xs font-medium">{dist_view}</div>
        </div>
      </div>

      {/* 仪表盘/进度条 */}
      <div className="relative pt-2 pb-4">
        <div className="h-2 bg-secondary rounded-full overflow-hidden w-full relative">
          {/* 低估区 0-30 */}
          <div className="absolute left-0 top-0 h-full w-[30%] bg-green-500/20"></div>
          {/* 适中区 30-70 */}
          <div className="absolute left-[30%] top-0 h-full w-[40%] bg-yellow-500/20"></div>
          {/* 高估区 70-100 */}
          <div className="absolute left-[70%] top-0 h-full w-[30%] bg-red-500/20"></div>
          
          {/* 指针/标记 */}
          <div 
            className={`absolute top-0 h-full w-1 ${bgClass} z-10 transition-all duration-1000`}
            style={{ left: `${Math.min(Math.max(pe_percentile, 0), 100)}%` }}
          ></div>
        </div>
        <div className="flex justify-between text-[10px] text-muted-foreground mt-1 px-0.5">
          <span>0%</span>
          <span>历史分位: {pe_percentile.toFixed(1)}%</span>
          <span>100%</span>
        </div>
      </div>

      <div className="text-[10px] text-muted-foreground/60 flex justify-between border-t border-border pt-2 mt-2">
        <span>数据覆盖: {history_years}年</span>
        <span>更新: {data_date}</span>
      </div>
    </div>
  );
}
