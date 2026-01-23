"use client";

import { useState, useEffect, useMemo } from "react";
import { 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  ReferenceArea
} from "recharts";
import { fetchClient, type ETFHistoryItem } from "@/lib/api";
import { cn } from "@/lib/utils";

export type Period = "1y" | "3y" | "5y" | "all";

interface ETFChartProps {
  code: string;
  period: Period;
  onPeriodChange: (p: Period) => void;
  drawdownInfo?: {
      start?: string;
      trough?: string;
      end?: string | null;
      value?: number;
  };
}

function calculateDaysDiff(start: string, end: string): number {
    const startDate = new Date(start);
    const endDate = new Date(end);
    const diffTime = Math.abs(endDate.getTime() - startDate.getTime());
    return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
}


function CustomAreaLabel(props: any) {
  // Use labelPosition instead of position to avoid potential conflict with Recharts injected props
  const { viewBox, value, fill, fontSize, fontWeight, dy, labelPosition } = props;
  const { x, width, y, height } = viewBox;
  
  if (!viewBox || !value) return null;

  const centerX = x + width / 2;
  // Ensure text stays visible on the left side
  // 45px padding allows for text to be half visible if centered at 45px (text width approx 70-80px)
  const safeX = Math.max(centerX, 45); 

  let textY = y;
  if (labelPosition === "insideBottom") {
    textY = y + height; 
  }
  
  if (dy) textY += dy;

  return (
    <text
      x={safeX}
      y={textY}
      fill={fill}
      fontSize={fontSize}
      fontWeight={fontWeight}
      textAnchor="middle"
      dominantBaseline={labelPosition === "insideTop" ? "hanging" : "auto"} 
    >
      {value}
    </text>
  );
}

export function ETFChart({ code, period, onPeriodChange, drawdownInfo }: ETFChartProps) {
  const [data, setData] = useState<ETFHistoryItem[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        const history = await fetchClient<ETFHistoryItem[]>(`/etf/${code}/history?period=daily`);
        setData(history);
      } catch (err) {
        console.error("Failed to load chart data", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [code]);

  const filteredData = useMemo(() => {
    if (!data.length) return [];
    
    const now = new Date();
    let startDate = new Date();
    
    switch (period) {
      case "1y":
        startDate.setFullYear(now.getFullYear() - 1);
        break;
      case "3y":
        startDate.setFullYear(now.getFullYear() - 3);
        break;
      case "5y":
        startDate.setFullYear(now.getFullYear() - 5);
        break;
      case "all":
        return data;
    }

    return data.filter(item => new Date(item.date) >= startDate);
  }, [data, period]);

  const { min, max } = useMemo(() => {
    if (!filteredData.length) return { min: 0, max: 0 };
    let min = Infinity;
    let max = -Infinity;
    for (const d of filteredData) {
      if (d.close < min) min = d.close;
      if (d.close > max) max = d.close;
    }
    const padding = (max - min) * 0.05;
    return { min: min - padding, max: max + padding };
  }, [filteredData]);

  const chartColor = "hsl(var(--primary))";

  return (
    <div className="w-full">
      {/* Period Switcher */}
      <div className="flex w-full items-center justify-between px-4 mb-4">
        {(["1y", "3y", "5y", "all"] as Period[]).map((p) => (
          <button
            key={p}
            onClick={() => onPeriodChange(p)}
            className={cn(
              "text-sm font-medium transition-colors",
              period === p 
                ? "rounded-full bg-primary/10 px-4 py-1 font-bold text-primary" 
                : "text-muted-foreground hover:text-primary px-2"
            )}
          >
            {p === "all" ? "全部" : p.replace("y", "年")}
          </button>
        ))}
      </div>

      {/* Chart */}
      <div className="h-[280px] w-full relative">
        {loading && data.length === 0 ? (
          <div className="h-full w-full bg-secondary/10 animate-pulse rounded-lg flex items-center justify-center text-muted-foreground text-sm">
            加载中...
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={filteredData} margin={{ top: 10, right: 0, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={chartColor} stopOpacity={0.2}/>
                  <stop offset="95%" stopColor={chartColor} stopOpacity={0}/>
                </linearGradient>
              </defs>
              {/* Dashed Grid Lines similar to design */}
              <CartesianGrid strokeDasharray="4 4" vertical={false} stroke="hsl(var(--muted-foreground))" opacity={0.1} />
              
              {/* Drawdown & Recovery Zones */}
              {drawdownInfo?.start && drawdownInfo?.trough && (
                  <ReferenceArea 
                      x1={drawdownInfo.start} 
                      x2={drawdownInfo.trough} 
                      y1={min} 
                      y2={max}
                      fill="var(--down)" 
                      fillOpacity={0.15}
                      ifOverflow="extendDomain"
                      label={
                        <CustomAreaLabel 
                          value={`回撤${(drawdownInfo.value ? drawdownInfo.value * 100 : 0).toFixed(1)}%`}
                          labelPosition="insideBottom"
                          fill="var(--down)"
                          fontSize={12}
                          fontWeight={600}
                          dy={-6}
                        />
                      }
                  />
              )}
              
              {drawdownInfo?.trough && (
                  <ReferenceArea 
                      x1={drawdownInfo.trough} 
                      x2={drawdownInfo.end || filteredData[filteredData.length - 1]?.date} 
                      y1={min} 
                      y2={max}
                      fill="var(--up)" 
                      fillOpacity={0.15}
                      ifOverflow="extendDomain"
                      label={
                        <CustomAreaLabel 
                          value={drawdownInfo.end 
                            ? `${calculateDaysDiff(drawdownInfo.trough, drawdownInfo.end)}天修复`
                            : `修复中${calculateDaysDiff(drawdownInfo.trough, filteredData[filteredData.length - 1]?.date || new Date().toISOString())}天+`}
                          labelPosition="insideTop"
                          fill="var(--up)"
                          fontSize={12}
                          fontWeight={600}
                          dy={6}
                        />
                      }
                  />
              )}

              <XAxis 
                dataKey="date" 
                hide 
              />
              <YAxis 
                domain={[min, max]} 
                orientation="right" 
                tick={{fontSize: 10, fill: "hsl(var(--muted-foreground))", fontWeight: 500}}
                tickFormatter={(val) => val.toFixed(2)}
                axisLine={false}
                tickLine={false}
                width={40}
              />
              <Tooltip
                content={({ active, payload, label }) => {
                  if (active && payload && payload.length) {
                    return (
                      <div className="bg-popover border border-border/50 px-3 py-2 rounded-lg shadow-xl text-xs ring-1 ring-black/5">
                        <p className="text-muted-foreground mb-1">{label}</p>
                        <p className="font-bold font-mono text-base text-foreground">
                          ¥{Number(payload[0].value).toFixed(3)}
                        </p>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Area 
                type="monotone" 
                dataKey="close" 
                stroke={chartColor} 
                strokeWidth={2.5}
                fillOpacity={1} 
                fill="url(#colorPrice)" 
                isAnimationActive={false} 
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
        
        <div className="absolute bottom-1 left-4 pointer-events-none">
          <p className="text-[10px] text-muted-foreground/70">价格已按前复权 (QFQ) 处理</p>
        </div>
      </div>
    </div>
  );
}
