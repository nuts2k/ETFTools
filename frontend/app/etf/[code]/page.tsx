"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { 
  ArrowLeft, 
  TrendingUp, 
  TrendingDown, 
  Plus, 
  Check, 
  Search, 
  Star, 
  Settings,
  Activity,
  ArrowDownCircle,
  PieChart
} from "lucide-react";
import { fetchClient, type ETFDetail, type ETFMetrics } from "@/lib/api";
import { ETFChart, type Period } from "@/components/ETFChart";
import ValuationCard from "@/components/ValuationCard";
import { useWatchlist } from "@/hooks/use-watchlist";
import { useSettings } from "@/hooks/use-settings";
import { cn } from "@/lib/utils";

export default function ETFDetailPage() {
  const params = useParams();
  const router = useRouter();
  const code = params.code as string;
  
  const { settings } = useSettings();

  const [info, setInfo] = useState<ETFDetail | null>(null);
  const [metrics, setMetrics] = useState<ETFMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [metricsLoading, setMetricsLoading] = useState(false);
  const [error, setError] = useState("");
  const [period, setPeriod] = useState<Period>("5y");

  const { isWatched, add, remove, isLoaded: isWatchlistLoaded } = useWatchlist();
  const watched = isWatched(code);

  const fetchInfo = async () => {
      try {
        const infoData = await fetchClient<ETFDetail>(`/etf/${code}/info`);
        setInfo(infoData);
        return infoData;
      } catch (err) {
        console.error("Failed to fetch info", err);
      }
  };

  useEffect(() => {
    async function initialLoad() {
      try {
        setLoading(true);
        await fetchInfo();
      } catch (err) {
        setError("Failed to load ETF data");
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    initialLoad();
  }, [code]);

  useEffect(() => {
    async function loadMetrics() {
        if (!code) return;
        try {
            setMetricsLoading(true);
            const data = await fetchClient<ETFMetrics>(`/etf/${code}/metrics?period=${period}`);
            setMetrics(data);
        } catch (err) {
            console.error("Failed to load metrics", err);
            // Optionally clear metrics or show error in metrics section
        } finally {
            setMetricsLoading(false);
        }
    }
    loadMetrics();
  }, [code, period]);

  // Auto Refresh Logic
  useEffect(() => {
    if (!settings.refreshRate || settings.refreshRate <= 0) return;
    
    const interval = setInterval(() => {
        fetchInfo();
    }, settings.refreshRate * 1000);

    return () => clearInterval(interval);
  }, [code, settings.refreshRate]);

  const toggleWatchlist = () => {
    if (!info) return;
    if (watched) {
      remove(code);
    } else {
      add({
        code: info.code,
        name: info.name,
        price: info.price,
        change_pct: info.change_pct,
        volume: info.volume
      });
    }
  };

  if (error && !info) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[100dvh] p-4 text-center bg-background">
        <h2 className="text-xl font-bold mb-2">出错了</h2>
        <p className="text-muted-foreground mb-6">{error || "未找到该 ETF"}</p>
        <button onClick={() => router.back()} className="text-primary font-medium hover:underline">
          返回上一页
        </button>
      </div>
    );
  }

  const isUp = info?.change_pct ? info.change_pct > 0 : false;
  const isDown = info?.change_pct ? info.change_pct < 0 : false;
  const changeColor = isUp ? "text-up" : isDown ? "text-down" : "text-foreground";
  const bgColor = isUp ? "bg-up/10" : isDown ? "bg-down/10" : "bg-muted";
  const iconColor = isUp ? "text-up" : isDown ? "text-down" : "text-muted-foreground";

  return (
    <div className="min-h-[100dvh] bg-background pb-48 relative">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-background/95 backdrop-blur-md pt-safe border-b border-border/50 transition-all transform-gpu backface-hidden">
        <div className="flex h-14 items-center justify-center relative px-5">
          <button 
              onClick={() => router.back()} 
              className="absolute left-4 flex w-10 h-10 items-center justify-center rounded-full text-foreground hover:bg-secondary transition-colors -ml-2"
          >
            <ArrowLeft className="h-6 w-6" />
          </button>
          <h2 className="text-lg font-bold tracking-tight text-foreground">{code}</h2>
        </div>
      </header>

      {/* Hero Section */}
      <div className="flex flex-col items-center px-4 pt-4 pb-2 text-center">
        <div className="flex items-center gap-2 mb-3">
             <span className="px-2 py-0.5 rounded-md bg-secondary text-muted-foreground text-[10px] font-bold tracking-wider">
                {info?.code.startsWith("5") ? "SH" : "SZ"}
             </span>
             <span className="px-2 py-0.5 rounded-md bg-secondary/50 text-muted-foreground/80 text-[10px] font-medium">
                {info?.market || "已收盘"}
             </span>
        </div>

        {loading ? (
            <div className="h-8 w-48 bg-secondary/50 animate-pulse rounded-lg mb-2" />
        ) : (
            <h1 className="text-xl font-medium text-muted-foreground">{info?.name}</h1>
        )}
        
        <div className="mt-2 flex flex-col items-center">
          {loading ? (
              <div className="h-12 w-40 bg-secondary/50 animate-pulse rounded-lg mb-2" />
          ) : (
              <span className="text-[48px] font-bold tracking-tighter leading-none text-foreground tabular-nums">
                {info?.price.toFixed(3)}
              </span>
          )}
          
          {loading ? (
              <div className="mt-3 h-7 w-24 bg-secondary/50 animate-pulse rounded-full" />
          ) : (
              <div className="mt-3 flex items-center gap-2">
                <div className={cn("flex items-center gap-1 rounded-full px-3 py-1 font-bold", bgColor)}>
                    {isUp ? <TrendingUp className={cn("h-4 w-4", iconColor)} /> : <TrendingDown className={cn("h-4 w-4", iconColor)} />}
                    <span className={cn("text-sm tabular-nums", changeColor)}>
                    {isUp ? "+" : ""}{info?.change_pct}%
                    </span>
                </div>
                <span className="text-xs text-muted-foreground/60 font-medium tabular-nums">
                    {info?.update_time?.split(' ')[1] || "--:--"}
                </span>
              </div>
          )}
        </div>
      </div>

      {/* Chart Section */}
      <div className="mt-4 w-full px-0">
         <ETFChart 
            code={code} 
            period={period} 
            onPeriodChange={setPeriod}
            drawdownInfo={metrics ? {
                start: metrics.mdd_start,
                trough: metrics.mdd_trough,
                end: metrics.mdd_end,
                value: metrics.max_drawdown
            } : undefined}
         />
      </div>

      <div className="h-2 w-full bg-secondary/30 mt-6" />

      <div className="flex flex-col px-4 py-6">
        {/* Valuation Card with Loading State */}
        {(loading || metricsLoading || metrics?.valuation) && (
          <div className="mb-6">
            {loading || metricsLoading ? (
               <div className="h-24 w-full bg-secondary/50 animate-pulse rounded-xl" />
            ) : metrics?.valuation ? (
               <ValuationCard data={metrics.valuation} />
            ) : null}
          </div>
        )}

        <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-muted-foreground">核心指标</h3>
        <div className="grid grid-cols-2 gap-3">
           <MetricCard 
             label="区间总收益" 
             value={metrics ? `${(metrics.total_return * 100).toFixed(2)}%` : "--"}
             subValue={metrics ? "相对指数 +0.0%" : ""}
             color={metrics && metrics.total_return > 0 ? "text-up" : "text-down"}
             icon={PieChart}
             loading={metricsLoading || loading}
           />
            <MetricCard 
              label="年化收益 (CAGR)" 
              value={metrics ? `${(metrics.cagr * 100).toFixed(2)}%` : "--"}
              subValue={(() => {
                if (!metrics) return "--";
                if (period === "all") return "成立以来年化";
                
                const requestedYears = period === "1y" ? 1 : period === "3y" ? 3 : 5;
                const actualYears = metrics.actual_years ?? 0;
                
                // 如果实际时长明显少于请求时长（少于 95%），显示实际时长
                if (actualYears < requestedYears * 0.95) {
                  return actualYears < 1.0 
                    ? `成立以来 (${(actualYears * 12).toFixed(1)}个月) 年化`
                    : `成立以来 (${actualYears.toFixed(1)}年) 年化`;
                }
                
                return period === "1y" ? "1年年化" : period === "3y" ? "3年年化" : "5年年化";
              })()}
              color={metrics && metrics.cagr >= 0 ? "text-up" : "text-down"}
              icon={TrendingUp}
              loading={metricsLoading || loading}
            />
           <MetricCard 
             label="最大回撤" 
             value={metrics ? `${(metrics.max_drawdown * 100).toFixed(2)}%` : "--"}
             subValue={metrics?.mdd_date}
             color="text-down"
             icon={ArrowDownCircle}
             loading={metricsLoading || loading}
           />
           <MetricCard 
             label="波动率" 
             value={metrics ? `${(metrics.volatility * 100).toFixed(2)}%` : "--"}
             subValue={metrics ? `风险等级: ${metrics.risk_level}` : ""}
             icon={Activity}
             loading={metricsLoading || loading}
           />
           <MetricCard 
             label="ATR (14日)" 
             value={metrics?.atr !== undefined && metrics.atr !== null ? metrics.atr.toFixed(4) : "--"}
             subValue="平均真实波幅"
             icon={Activity}
             loading={metricsLoading || loading}
           />
           <MetricCard 
             label={
                 metrics?.effective_drawdown_days && metrics?.drawdown_days && metrics.effective_drawdown_days < metrics.drawdown_days
                    ? `成立以来回撤 (${metrics.effective_drawdown_days}日)`
                    : (metrics?.drawdown_days ? `近${metrics.drawdown_days}日回撤` : "短期回撤")
             } 
             value={metrics?.current_drawdown !== undefined && metrics.current_drawdown !== null ? `${(metrics.current_drawdown * 100).toFixed(2)}%` : "--"}
             subValue={
                metrics?.current_drawdown_peak_date 
                  ? `峰值:${metrics.current_drawdown_peak_date}(距今${metrics.days_since_peak}天)` 
                  : "距区间最高点"
             }
             color={metrics && (metrics.current_drawdown || 0) < 0 ? "text-down" : "text-foreground"}
             icon={TrendingDown}
             loading={metricsLoading || loading}
           />
        </div>
      </div>

      {/* Bottom Action Bar - Floating */}
      <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-50">
          <button 
            onClick={toggleWatchlist}
            className={cn(
                "flex items-center justify-center gap-2 rounded-full px-8 py-3.5 text-[15px] font-bold shadow-2xl transition-all active:scale-95 ring-1 ring-white/10 backdrop-blur-xl",
                watched 
                    ? "bg-secondary/90 text-foreground hover:bg-secondary border border-border/50" 
                    : "bg-primary text-primary-foreground hover:bg-primary/90 shadow-primary/40"
            )}
          >
            {watched ? (
                <>
                    <Check className="h-5 w-5" />
                    <span>已关注</span>
                </>
            ) : (
                <>
                    <Plus className="h-5 w-5" />
                    <span>加入自选</span>
                </>
            )}
          </button>
      </div>
    </div>
  );
}

function MetricCard({ label, value, subValue, color, icon: Icon, loading }: any) {
  return (
    <div className="flex flex-col rounded-2xl bg-card p-5 shadow-sm transition-all hover:shadow-md">
      <div className="flex items-center gap-2 mb-3">
        {Icon && <div className="p-1.5 rounded-md bg-secondary/50"><Icon className="h-3.5 w-3.5 text-muted-foreground" /></div>}
        <span className="text-xs font-bold text-muted-foreground uppercase tracking-wide">{label}</span>
      </div>
      <div className="mt-auto">
        {loading ? (
            <div className="h-8 w-24 bg-secondary/50 animate-pulse rounded mb-1" />
        ) : (
            <span className={cn("text-2xl font-bold tracking-tight tabular-nums block", color || "text-foreground")}>
                {value}
            </span>
        )}
        {subValue && !loading && (
            <span className="text-[11px] font-medium text-muted-foreground/60 mt-1 block truncate">
                {subValue}
            </span>
        )}
      </div>
    </div>
  );
}
