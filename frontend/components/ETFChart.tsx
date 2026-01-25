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

  // Check for invalid coordinates
  if (isNaN(x) || isNaN(width) || isNaN(y) || isNaN(height)) return null;

  const centerX = x + width / 2;
  if (isNaN(centerX)) return null;

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

  const xAxisTicks = useMemo(() => {
    if (!filteredData.length) return [];
    if (filteredData.length <= 5) return filteredData.map(d => d.date);

    const indices = [0, Math.floor(filteredData.length / 4), Math.floor(2 * filteredData.length / 4), Math.floor(3 * filteredData.length / 4), filteredData.length - 1];
    return indices.map(i => filteredData[i].date);
  }, [filteredData]);

  const chartColor = "hsl(var(--primary))";

  const CustomXAxisTick = (props: any) => {
    const { x, y, payload, index } = props;

    let textAnchor: "start" | "middle" | "end" = "middle";
    if (index === 0) textAnchor = "start";
    else if (index === xAxisTicks.length - 1) textAnchor = "end";

    const date = new Date(payload.value);
    const month = (date.getMonth() + 1).toString().padStart(2, '0');
    let formattedDate: string;
    if (period === "1y") {
      const day = date.getDate().toString().padStart(2, '0');
      formattedDate = `${month}-${day}`;
    } else {
      const year = date.getFullYear().toString().slice(2);
      formattedDate = `${year}-${month}`;
    }

    return (
      <g transform={`translate(${x},${y})`}>
        <text
          dy={16}
          fontSize={10}
          fill="hsl(var(--muted-foreground))"
          fontWeight={500}
          textAnchor={textAnchor}
        >
          {formattedDate}
        </text>
      </g>
    );
  };

  return (
    <div className="w-full">
      {/* Period Switcher - Segmented Control */}
      <div className="flex w-full px-4 mb-6 justify-center">
        <div className="flex w-full max-w-[320px] bg-secondary/40 rounded-xl p-1.5">
          {(["1y", "3y", "5y", "all"] as Period[]).map((p) => (
            <button
              key={p}
              onClick={() => onPeriodChange(p)}
              className={cn(
                "flex-1 text-xs font-bold py-1.5 rounded-lg transition-all",
                period === p 
                  ? "bg-background text-foreground shadow-sm scale-[1.02]" 
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {p === "all" ? "全部" : p.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Chart */}
      <div className="h-[280px] w-full relative">
        {loading && data.length === 0 ? (
          <div className="h-full w-full bg-secondary/10 animate-pulse rounded-lg flex items-center justify-center text-muted-foreground text-sm">
            加载中...
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={filteredData} margin={{ top: 10, right: 5, left: 5, bottom: 20 }}>
              <defs>
                <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={chartColor} stopOpacity={0.35}/>
                  <stop offset="95%" stopColor={chartColor} stopOpacity={0}/>
                </linearGradient>
              </defs>
              {/* Dashed Grid Lines similar to design */}
              <CartesianGrid strokeDasharray="2 4" vertical={false} stroke="hsl(var(--muted-foreground))" opacity={0.15} />
              
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
                 ticks={xAxisTicks}
                 interval={0}
                 tick={<CustomXAxisTick />}
                 axisLine={false}
                 tickLine={false}
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
                cursor={{ stroke: 'hsl(var(--muted-foreground))', strokeWidth: 1, strokeDasharray: '4 4' }}
                content={({ active, payload, label }) => {
                  if (active && payload && payload.length) {
                    return (
                      <div className="bg-popover/90 backdrop-blur-md border border-border/50 px-3 py-2 rounded-xl shadow-xl text-xs ring-1 ring-black/5">
                        <p className="text-muted-foreground mb-1">{label}</p>
                        <p className="font-bold font-mono text-base text-foreground tracking-tight">
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
                strokeWidth={2}
                fillOpacity={1} 
                fill="url(#colorPrice)" 
                isAnimationActive={false} 
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="mt-2 px-4">
        <p className="text-[10px] text-muted-foreground/70">价格已按前复权 (QFQ) 处理</p>
      </div>
    </div>
  );
}
