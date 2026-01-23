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

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen text-muted-foreground bg-background">
        加载中...
      </div>
    );
  }

  if (error || !info) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen p-4 text-center bg-background">
        <h2 className="text-xl font-bold mb-2">出错了</h2>
        <p className="text-muted-foreground mb-6">{error || "未找到该 ETF"}</p>
        <button onClick={() => router.back()} className="text-primary font-medium hover:underline">
          返回上一页
        </button>
      </div>
    );
  }

  const isUp = info.change_pct > 0;
  const isDown = info.change_pct < 0;
  const changeColor = isUp ? "text-up" : isDown ? "text-down" : "text-foreground";
  const bgColor = isUp ? "bg-up/10" : isDown ? "bg-down/10" : "bg-muted";
  const iconColor = isUp ? "text-up" : isDown ? "text-down" : "text-muted-foreground";

  return (
    <div className="min-h-screen bg-background pb-48 relative">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-background/95 backdrop-blur-md pt-safe border-b border-border/50 transition-all">
        <div className="flex h-14 items-center justify-center relative px-5">
          <button 
              onClick={() => router.back()} 
              className="absolute left-4 flex w-10 h-10 items-center justify-center rounded-full text-foreground hover:bg-secondary transition-colors -ml-2"
          >
            <ArrowLeft className="h-6 w-6" />
          </button>
          <h2 className="text-lg font-bold tracking-tight text-foreground">{info.code}</h2>
        </div>
      </header>

      {/* Hero Section */}
      <div className="flex flex-col items-center px-4 pt-6 pb-2 text-center">
        <h1 className="text-xl font-semibold leading-tight text-foreground/90">{info.name}</h1>
        <div className="mt-4 flex flex-col items-center">
          <span className="text-[40px] font-bold tracking-tight leading-none text-foreground tabular-nums">
            ¥{info.price.toFixed(3)}
          </span>
          <div className={cn("mt-2 flex items-center gap-1 rounded-full px-3 py-1", bgColor)}>
            {isUp ? <TrendingUp className={cn("h-4 w-4", iconColor)} /> : <TrendingDown className={cn("h-4 w-4", iconColor)} />}
            <span className={cn("text-sm font-bold tabular-nums", changeColor)}>
              {isUp ? "+" : ""}{info.change_pct}%
            </span>
          </div>
        </div>
        <p className="mt-3 text-xs text-muted-foreground">
            {info.update_time} • {info.market || "已收盘"}
        </p>
      </div>

      {/* Chart Section */}
      <div className="mt-4 w-full px-0">
         <ETFChart code={code} period={period} onPeriodChange={setPeriod} />
      </div>

      <div className="h-2 w-full bg-secondary/30 mt-6" />

      {/* Metrics Section */}
      <div className="flex flex-col px-4 py-6">
        <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-muted-foreground">核心指标</h3>
        <div className="grid grid-cols-2 gap-3">
           <MetricCard 
             label="区间总收益" 
             value={metrics ? `${(metrics.total_return * 100).toFixed(2)}%` : "--"}
             subValue={metrics ? "相对指数 +0.0%" : ""}
             color={metrics && metrics.total_return > 0 ? "text-up" : "text-down"}
             icon={PieChart}
             loading={metricsLoading}
           />
           <MetricCard 
             label="年化收益 (CAGR)" 
             value={metrics ? `${(metrics.cagr * 100).toFixed(2)}%` : "--"}
             subValue={
               period === "all" ? "成立以来年化" : 
               period === "1y" ? "1年年化" :
               period === "3y" ? "3年年化" :
               "5年年化"
             }
             color="text-up"
             icon={TrendingUp}
             loading={metricsLoading}
           />
           <MetricCard 
             label="最大回撤" 
             value={metrics ? `${(metrics.max_drawdown * 100).toFixed(2)}%` : "--"}
             subValue={metrics?.mdd_date}
             color="text-down"
             icon={ArrowDownCircle}
             loading={metricsLoading}
           />
           <MetricCard 
             label="波动率" 
             value={metrics ? `${(metrics.volatility * 100).toFixed(2)}%` : "--"}
             subValue={metrics ? `风险等级: ${metrics.risk_level}` : ""}
             icon={Activity}
             loading={metricsLoading}
           />
        </div>
      </div>

      {/* Bottom Action Bar */}
      <div className="fixed bottom-0 left-0 right-0 z-50 mx-auto w-full bg-background/95 backdrop-blur-md border-t border-border pb-safe">
        {/* Action Button */}
        <div className="px-4 py-3">
          <button 
            onClick={toggleWatchlist}
            className={cn(
                "flex w-full items-center justify-center gap-2 rounded-xl py-3.5 text-[15px] font-bold shadow-lg transition-all active:scale-[0.98]",
                watched 
                    ? "bg-secondary text-foreground hover:bg-secondary/80" 
                    : "bg-primary text-primary-foreground hover:bg-primary/90 shadow-primary/25"
            )}
          >
            {watched ? (
                <>
                    <Check className="h-5 w-5" />
                    <span>已添加自选</span>
                </>
            ) : (
                <>
                    <Plus className="h-5 w-5" />
                    <span>加入自选</span>
                </>
            )}
          </button>
        </div>

        {/* Static Nav Links */}
        <div className="grid grid-cols-3 h-14 border-t border-border/10 pb-2">
            <Link href="/" className="flex flex-col items-center justify-center gap-1 text-muted-foreground hover:text-primary transition-colors">
                <Star className="h-6 w-6" />
                <span className="text-[10px] font-medium">自选</span>
            </Link>
            <Link href="/search" className="flex flex-col items-center justify-center gap-1 text-muted-foreground hover:text-primary transition-colors">
                <Search className="h-6 w-6" />
                <span className="text-[10px] font-medium">搜索</span>
            </Link>
            <Link href="/settings" className="flex flex-col items-center justify-center gap-1 text-muted-foreground hover:text-primary transition-colors">
                <Settings className="h-6 w-6" />
                <span className="text-[10px] font-medium">设置</span>
            </Link>
        </div>
      </div>
    </div>
  );
}

function MetricCard({ label, value, subValue, color, icon: Icon, loading }: any) {
  return (
    <div className="flex flex-col rounded-xl bg-card p-4 shadow-sm ring-1 ring-border/50">
      <div className="flex items-center gap-1.5 mb-2">
        {Icon && <Icon className="h-3 w-3 text-muted-foreground" />}
        <span className="text-xs font-medium text-muted-foreground">{label}</span>
      </div>
      <div className="mt-1 flex items-baseline gap-1">
        {loading ? (
            <div className="h-7 w-20 bg-secondary/50 animate-pulse rounded" />
        ) : (
            <span className={cn("text-xl font-bold tracking-tight tabular-nums", color || "text-foreground")}>
                {value}
            </span>
        )}
      </div>
      {subValue && !loading && (
        <span className="text-[10px] text-muted-foreground/80 mt-1 truncate">
            {subValue}
        </span>
      )}
    </div>
  );
}
