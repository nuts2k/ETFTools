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
  ReferenceLine
} from "recharts";
import { fetchClient, type ETFHistoryItem } from "@/lib/api";
import { cn } from "@/lib/utils";

interface ETFChartProps {
  code: string;
}

type Period = "1y" | "3y" | "5y" | "all";

export function ETFChart({ code }: ETFChartProps) {
  const [period, setPeriod] = useState<Period>("5y");
  const [data, setData] = useState<ETFHistoryItem[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        // Backend API currently accepts period="daily" and returns full history
        // We might need to filter on client side or update backend to support "1y" etc.
        // For now, let's fetch full history and filter on client to ensure smooth transitions
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

  // Client-side filtering for periods
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

  // Calculate min/max for Y-axis domain
  const { min, max } = useMemo(() => {
    if (!filteredData.length) return { min: 0, max: 0 };
    let min = Infinity;
    let max = -Infinity;
    for (const d of filteredData) {
      if (d.close < min) min = d.close;
      if (d.close > max) max = d.close;
    }
    // Add some padding
    const padding = (max - min) * 0.05;
    return { min: min - padding, max: max + padding };
  }, [filteredData]);

  // Color logic (red for up, green for down based on whole period)
  // Or just use theme color. PRD says "Red=Up, Green=Down".
  // Let's use blue (primary) for the line to be neutral, or follow trend?
  // Usually price charts use a single color (e.g. Blue or Gold) unless it's a candlestick.
  // Let's use the Primary Blue (#1269e2) defined in globals.
  const chartColor = "hsl(var(--primary))";

  return (
    <div className="w-full space-y-4">
      {/* Period Switcher */}
      <div className="flex justify-end space-x-2">
        {(["1y", "3y", "5y", "all"] as Period[]).map((p) => (
          <button
            key={p}
            onClick={() => setPeriod(p)}
            className={cn(
              "px-3 py-1 text-xs font-medium rounded-full transition-colors",
              period === p 
                ? "bg-primary text-primary-foreground" 
                : "bg-secondary text-secondary-foreground hover:bg-secondary/80"
            )}
          >
            {p === "all" ? "全部" : p.replace("y", "年")}
          </button>
        ))}
      </div>

      {/* Chart */}
      <div className="h-[250px] w-full">
        {loading && data.length === 0 ? (
          <div className="h-full w-full bg-secondary/20 animate-pulse rounded-lg flex items-center justify-center text-muted-foreground text-sm">
            加载图表中...
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={filteredData}>
              <defs>
                <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={chartColor} stopOpacity={0.3}/>
                  <stop offset="95%" stopColor={chartColor} stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" opacity={0.5} />
              <XAxis 
                dataKey="date" 
                hide 
                // tickFormatter={(val) => new Date(val).getFullYear().toString()}
              />
              <YAxis 
                domain={[min, max]} 
                orientation="right" 
                tick={{fontSize: 10, fill: "hsl(var(--muted-foreground))"}}
                tickFormatter={(val) => val.toFixed(2)}
                axisLine={false}
                tickLine={false}
                width={35}
              />
              <Tooltip
                content={({ active, payload, label }) => {
                  if (active && payload && payload.length) {
                    return (
                      <div className="bg-popover border border-border px-3 py-2 rounded-lg shadow-lg text-xs">
                        <p className="text-muted-foreground mb-1">{label}</p>
                        <p className="font-bold font-mono text-base text-foreground">
                          {Number(payload[0].value).toFixed(3)}
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
                isAnimationActive={false} // Disable animation for clearer updates
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
      
      <div className="text-[10px] text-muted-foreground text-center">
        * 价格已按前复权 (QFQ) 处理
      </div>
    </div>
  );
}
