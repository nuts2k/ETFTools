"use client";

import { useState, useEffect, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Star, AlertTriangle, TrendingUp, Activity, ArrowDownCircle } from "lucide-react";
import { fetchClient, type ETFDetail, type ETFMetrics } from "@/lib/api";
import { ETFChart } from "@/components/ETFChart";
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
  const [error, setError] = useState("");

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
        // Fetch Info and Metrics in parallel
        await Promise.all([
          fetchInfo(),
          fetchClient<ETFMetrics>(`/etf/${code}/metrics`)
            .then(setMetrics)
            .catch(() => null)
        ]);
      } catch (err) {
        setError("Failed to load ETF data");
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    initialLoad();
  }, [code]);

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
      <div className="flex items-center justify-center min-h-screen text-muted-foreground">
        加载中...
      </div>
    );
  }

  if (error || !info) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen p-4 text-center">
        <AlertTriangle className="h-12 w-12 text-destructive mb-4" />
        <h2 className="text-xl font-bold mb-2">出错了</h2>
        <p className="text-muted-foreground mb-6">{error || "未找到该 ETF"}</p>
        <button onClick={() => router.back()} className="text-primary font-medium hover:underline">
          返回上一页
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background pb-safe">
      {/* Navbar */}
      <div className="sticky top-0 z-10 flex items-center justify-between px-4 h-14 bg-background/80 backdrop-blur border-b">
        <button onClick={() => router.back()} className="p-2 -ml-2 text-foreground/80 hover:text-foreground">
          <ArrowLeft className="h-6 w-6" />
        </button>
        <div className="flex flex-col items-center">
          <span className="text-sm font-bold">{info.code}</span>
          <span className="text-[10px] text-muted-foreground">{info.name}</span>
        </div>
        <div className="w-8" /> {/* Spacer for centering */}
      </div>

      <div className="px-4 py-6 space-y-6">
        {/* Header Price */}
        <div className="flex flex-col items-center">
          <h1 className={cn(
            "text-4xl font-mono font-bold tracking-tighter",
            info.change_pct > 0 ? "text-up" : info.change_pct < 0 ? "text-down" : "text-foreground"
          )}>
            {info.price.toFixed(3)}
          </h1>
          <div className="flex items-center gap-2 mt-1">
             <span className={cn(
              "text-sm font-medium px-2 py-0.5 rounded-full",
              info.change_pct > 0 ? "bg-up/10 text-up" : info.change_pct < 0 ? "bg-down/10 text-down" : "bg-muted text-muted-foreground"
            )}>
              {info.change_pct > 0 ? "+" : ""}{info.change_pct}%
            </span>
            <span className="text-xs text-muted-foreground">
               {info.update_time.split(" ")[1]}
            </span>
          </div>
        </div>

        {/* Chart */}
        <div className="bg-card rounded-xl p-2 border shadow-sm">
          <ETFChart code={code} />
        </div>

        {/* Metrics Grid */}
        <div className="grid grid-cols-2 gap-3">
          <MetricCard 
            label="年化收益 (5年)" 
            value={metrics ? `${(metrics.cagr * 100).toFixed(2)}%` : "--"} 
            icon={TrendingUp}
            color={metrics && metrics.cagr > 0 ? "text-up" : "text-foreground"}
          />
          <MetricCard 
            label="最大回撤" 
            value={metrics ? `${(metrics.max_drawdown * 100).toFixed(2)}%` : "--"} 
            subValue={metrics?.mdd_date}
            icon={ArrowDownCircle}
            color="text-down" // Drawdown is always bad/down
          />
          <MetricCard 
            label="波动率" 
            value={metrics ? `${(metrics.volatility * 100).toFixed(2)}%` : "--"} 
            subValue={metrics?.risk_level}
            icon={Activity}
          />
          <MetricCard 
            label="区间总收益" 
            value={metrics ? `${(metrics.total_return * 100).toFixed(2)}%` : "--"} 
            icon={Star}
            color={metrics && metrics.total_return > 0 ? "text-up" : "text-down"}
          />
        </div>
      </div>

      {/* Floating Action Button (Watchlist) */}
      <div className="fixed bottom-6 right-6 z-20">
        <button
          onClick={toggleWatchlist}
          disabled={!isWatchlistLoaded}
          className={cn(
            "h-14 w-14 rounded-full shadow-lg flex items-center justify-center transition-all active:scale-95",
            watched ? "bg-secondary text-primary border-2 border-primary" : "bg-primary text-primary-foreground"
          )}
        >
          <Star className={cn("h-6 w-6", watched && "fill-current")} />
        </button>
      </div>
    </div>
  );
}

function MetricCard({ label, value, subValue, icon: Icon, color }: any) {
  return (
    <div className="bg-card p-4 rounded-xl border shadow-sm flex flex-col justify-between">
      <div className="flex items-center gap-2 mb-2 text-muted-foreground">
        <Icon className="h-4 w-4" />
        <span className="text-xs font-medium">{label}</span>
      </div>
      <div>
        <div className={cn("text-lg font-bold font-mono", color)}>{value}</div>
        {subValue && <div className="text-[10px] text-muted-foreground mt-0.5">{subValue}</div>}
      </div>
    </div>
  );
}
