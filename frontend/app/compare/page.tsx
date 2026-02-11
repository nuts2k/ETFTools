"use client";

import { useState, useEffect, useRef, useMemo, useCallback, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Plus, X, Search as SearchIcon, Loader2 } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { useDebounce } from "@/hooks/use-debounce";
import { fetchClient, type CompareData, type CompareMetrics, type ETFItem } from "@/lib/api";
import { TAG_COLORS } from "@/lib/tag-colors";
import { cn } from "@/lib/utils";

// 线条颜色（与 chip 颜色对应，充当图例）
const LINE_COLORS = ["#3b82f6", "#a855f7", "#f97316"] as const;

// 搜索页标签按钮专用 ring 边框
const TAG_RING: Record<string, string> = {
  type: "ring-1 ring-blue-500/20 dark:ring-blue-400/20",
  industry: "ring-1 ring-purple-500/20 dark:ring-purple-400/20",
  strategy: "ring-1 ring-amber-500/20 dark:ring-amber-400/20",
  special: "ring-1 ring-border/50",
};

type Period = "1y" | "3y" | "5y" | "all";
type SelectedETF = { code: string; name: string };

function CompareContent() {
  const searchParams = useSearchParams();
  const router = useRouter();

  // --- 状态 ---
  const [selectedETFs, setSelectedETFs] = useState<SelectedETF[]>([]);
  const [period, setPeriod] = useState<Period>("3y");
  const [showSearch, setShowSearch] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<ETFItem[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [selectedTag, setSelectedTag] = useState<string | null>(null);
  const [popularTags, setPopularTags] = useState<Array<{label: string; group: string}>>([]);

  const [compareData, setCompareData] = useState<CompareData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const debouncedQuery = useDebounce(searchQuery, 300);
  const searchAbortRef = useRef<AbortController | null>(null);
  const compareAbortRef = useRef<AbortController | null>(null);

  // --- URL 状态同步：初始化 ---
  useEffect(() => {
    const codesParam = searchParams.get("codes");
    const periodParam = searchParams.get("period") as Period | null;
    if (periodParam && ["1y", "3y", "5y", "all"].includes(periodParam)) {
      setPeriod(periodParam);
    }
    if (codesParam) {
      const codes = codesParam.split(",").filter(c => /^\d{6}$/.test(c)).slice(0, 3);
      if (codes.length >= 2) {
        setSelectedETFs(codes.map(code => ({ code, name: code })));
      }
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // --- URL 状态同步：更新 URL ---
  const updateURL = useCallback((etfs: SelectedETF[], p: Period) => {
    if (etfs.length >= 2) {
      const codes = etfs.map(e => e.code).join(",");
      router.replace(`/compare?codes=${codes}&period=${p}`, { scroll: false });
    } else {
      router.replace("/compare", { scroll: false });
    }
  }, [router]);

  // --- 加载热门标签 ---
  useEffect(() => {
    fetchClient<Array<{label: string; group: string}>>("/etf/tags/popular")
      .then(setPopularTags)
      .catch(() => {});
  }, []);

  // --- 搜索逻辑（复用搜索页模式）---
  useEffect(() => {
    async function doSearch() {
      if (!debouncedQuery && !selectedTag) {
        setSearchResults([]);
        return;
      }
      searchAbortRef.current?.abort();
      const controller = new AbortController();
      searchAbortRef.current = controller;
      setSearchLoading(true);
      try {
        const url = selectedTag
          ? `/etf/search?tag=${encodeURIComponent(selectedTag)}`
          : `/etf/search?q=${encodeURIComponent(debouncedQuery)}`;
        const data = await fetchClient<ETFItem[]>(url, { signal: controller.signal });
        setSearchResults(data);
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
      } finally {
        setSearchLoading(false);
      }
    }
    doSearch();
    return () => { searchAbortRef.current?.abort(); };
  }, [debouncedQuery, selectedTag]);

  // --- 对比数据加载 ---
  const codesKey = selectedETFs.map(e => e.code).join(",");
  useEffect(() => {
    if (selectedETFs.length < 2) {
      setCompareData(null);
      return;
    }

    compareAbortRef.current?.abort();
    const controller = new AbortController();
    compareAbortRef.current = controller;
    setLoading(true);
    setError(null);

    const codesStr = selectedETFs.map(e => e.code).join(",");

    fetchClient<CompareData>(
      `/etf/compare?codes=${codesStr}&period=${period}`,
      { signal: controller.signal }
    )
      .then(setCompareData)
      .catch(err => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setError(err.message || "加载失败");
      })
      .finally(() => setLoading(false));

    return () => { controller.abort(); };
  }, [codesKey, period]); // eslint-disable-line react-hooks/exhaustive-deps

  // --- 从 compare API 回填 ETF 名称（独立 effect，避免循环依赖）---
  useEffect(() => {
    if (!compareData?.etf_names) return;
    const names = compareData.etf_names;
    setSelectedETFs(prev => {
      const needsUpdate = prev.some(e => names[e.code] && names[e.code] !== e.name);
      if (!needsUpdate) return prev;
      return prev.map(e => ({ ...e, name: names[e.code] || e.name }));
    });
  }, [compareData]);

  // --- 操作函数 ---
  const addETF = (etf: ETFItem) => {
    if (selectedETFs.length >= 3) return;
    if (selectedETFs.some(e => e.code === etf.code)) return;
    const next = [...selectedETFs, { code: etf.code, name: etf.name }];
    setSelectedETFs(next);
    setShowSearch(false);
    setSearchQuery("");
    setSelectedTag(null);
    updateURL(next, period);
  };

  const removeETF = (code: string) => {
    const next = selectedETFs.filter(e => e.code !== code);
    setSelectedETFs(next);
    updateURL(next, period);
  };

  const changePeriod = (p: Period) => {
    setPeriod(p);
    updateURL(selectedETFs, p);
  };

  // --- 图表数据转换 ---
  const chartData = useMemo(() => {
    if (!compareData) return [];
    return compareData.normalized.dates.map((date, i) => {
      const point: Record<string, string | number> = { date };
      for (const code of Object.keys(compareData.normalized.series)) {
        point[code] = compareData.normalized.series[code][i];
      }
      return point;
    });
  }, [compareData]);

  // --- 渲染 ---
  return (
    <div className="min-h-[100dvh] pb-20 bg-background">
      {/* 页面标题 */}
      <div className="sticky top-0 z-10 bg-background/85 backdrop-blur-md border-b border-border px-4 pt-safe">
        <h1 className="text-lg font-semibold py-3">ETF 对比</h1>
      </div>

      <div className="px-4 space-y-4 mt-4">
        {/* ETF 选择器 chips */}
        <div className="flex flex-wrap items-center gap-2">
          {selectedETFs.map((etf, i) => (
            <button
              key={etf.code}
              className="flex items-center gap-1.5 px-3 py-1.5 min-h-[44px] rounded-full text-sm font-medium text-white"
              style={{ backgroundColor: LINE_COLORS[i] }}
              onClick={() => removeETF(etf.code)}
            >
              {etf.name}
              <X className="h-3.5 w-3.5" />
            </button>
          ))}
          {selectedETFs.length < 3 && !showSearch && (
            <button
              aria-label="添加 ETF"
              className="flex items-center justify-center min-w-[44px] min-h-[44px] rounded-full border-2 border-dashed border-muted-foreground/30 text-muted-foreground hover:border-primary hover:text-primary transition-colors"
              onClick={() => setShowSearch(true)}
            >
              <Plus className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* 内联搜索 */}
        {showSearch && (
          <div className="space-y-2">
            <div className="relative">
              <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                autoFocus
                className="w-full pl-9 pr-9 py-2 rounded-lg border border-border bg-muted/50 text-sm outline-none focus:ring-2 focus:ring-primary/30"
                placeholder="搜索 ETF..."
                value={searchQuery}
                onChange={e => { setSearchQuery(e.target.value); setSelectedTag(null); }}
                onKeyDown={e => e.key === "Escape" && setShowSearch(false)}
              />
              <button
                className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-muted-foreground"
                onClick={() => { setShowSearch(false); setSearchQuery(""); setSelectedTag(null); }}
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* 标签横向滚动（输入文字时隐藏）*/}
            {!searchQuery && popularTags.length > 0 && (
              <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
                {popularTags.map(tag => {
                  const group = tag.group as keyof typeof TAG_COLORS;
                  const isActive = selectedTag === tag.label;
                  return (
                    <button
                      key={tag.label}
                      className={cn(
                        "shrink-0 px-3 py-1 rounded-full text-xs font-medium transition-all",
                        TAG_COLORS[group] || TAG_COLORS.special,
                        TAG_RING[group] || TAG_RING.special,
                        isActive && "ring-2 scale-105"
                      )}
                      onClick={() => {
                        setSelectedTag(prev => prev === tag.label ? null : tag.label);
                        setSearchQuery("");
                      }}
                    >
                      {tag.label}
                    </button>
                  );
                })}
              </div>
            )}

            {/* 搜索结果下拉列表 */}
            {(searchResults.length > 0 || searchLoading) && (
              <div className="border border-border rounded-lg bg-background shadow-sm max-h-48 overflow-y-auto">
                {searchLoading ? (
                  <div className="flex items-center justify-center py-4">
                    <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                  </div>
                ) : (
                  searchResults.map(etf => {
                    const alreadySelected = selectedETFs.some(e => e.code === etf.code);
                    return (
                      <button
                        key={etf.code}
                        disabled={alreadySelected}
                        className={cn(
                          "w-full flex items-center gap-3 px-4 py-3 text-sm text-left hover:bg-muted/50 transition-colors",
                          alreadySelected && "opacity-40 cursor-not-allowed"
                        )}
                        onClick={() => addETF(etf)}
                      >
                        <span className="text-muted-foreground font-mono text-xs">{etf.code}</span>
                        <span className="font-medium truncate">{etf.name}</span>
                      </button>
                    );
                  })
                )}
              </div>
            )}
          </div>
        )}

        {/* 引导文案 */}
        {selectedETFs.length < 2 && !showSearch && (
          <p className="text-center text-muted-foreground text-sm py-8">
            请添加至少 2 只 ETF 开始对比
          </p>
        )}

        {/* 时间切换 */}
        {selectedETFs.length >= 2 && (
          <div className="flex gap-2">
            {(["1y", "3y", "5y", "all"] as Period[]).map(p => (
              <button
                key={p}
                className={cn(
                  "flex-1 py-1.5 rounded-md text-sm font-medium transition-colors",
                  period === p
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:text-foreground"
                )}
                onClick={() => changePeriod(p)}
              >
                {p === "all" ? "全部" : p.toUpperCase()}
              </button>
            ))}
          </div>
        )}

        {/* 警告提示条 */}
        {compareData?.warnings && compareData.warnings.length > 0 && (
          <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg px-3 py-2 text-xs text-yellow-800 dark:text-yellow-200">
            {compareData.warnings.map((w, i) => <p key={i}>{w}</p>)}
          </div>
        )}

        {/* 加载状态 */}
        {loading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        )}

        {/* 错误状态 */}
        {error && (
          <div className="text-center text-destructive text-sm py-8">{error}</div>
        )}

        {/* 归一化走势图 */}
        {compareData && !loading && (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 10 }}
                  tickFormatter={v => {
                    const d = v as string;
                    return period === "1y" ? d.slice(5) : d.slice(2, 7);
                  }}
                  interval="preserveStartEnd"
                />
                <YAxis
                  tick={{ fontSize: 10 }}
                  tickFormatter={v => Math.round(v as number).toString()}
                  domain={["auto", "auto"]}
                  width={36}
                />
                <Tooltip
                  position={{ y: 0 }}
                  content={({ active, payload, label }) => {
                    if (!active || !payload?.length) return null;
                    return (
                      <div className="bg-background/95 backdrop-blur-sm border border-border rounded-lg px-3 py-2 shadow-sm text-xs">
                        <p className="text-muted-foreground mb-1">{label}</p>
                        {payload.map((p, i) => (
                          <p key={i} style={{ color: p.color }}>
                            {compareData.etf_names[p.dataKey as string] || p.dataKey}: {(p.value as number).toFixed(2)}
                          </p>
                        ))}
                      </div>
                    );
                  }}
                />
                {selectedETFs.map((etf, i) => (
                  <Line
                    key={etf.code}
                    type="monotone"
                    dataKey={etf.code}
                    stroke={LINE_COLORS[i]}
                    dot={false}
                    strokeWidth={1.5}
                    isAnimationActive={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* 相关性系数 */}
        {compareData && Object.keys(compareData.correlation).length > 0 && (
          <div className="space-y-1">
            <h3 className="text-sm font-medium text-muted-foreground">相关性系数</h3>
            <div className="space-y-1">
              {Object.entries(compareData.correlation).map(([pair, corr]) => {
                const [a, b] = pair.split("_");
                const nameA = compareData.etf_names[a] || a;
                const nameB = compareData.etf_names[b] || b;
                return (
                  <div key={pair} className="flex items-center justify-between text-sm">
                    <span>{nameA} vs {nameB}</span>
                    <span className={cn(
                      "font-mono font-medium",
                      corr >= 0.8 ? "text-red-500" : corr >= 0.4 ? "text-yellow-600" : "text-green-500"
                    )}>
                      {corr.toFixed(4)}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* 指标对比表格 */}
        {compareData?.metrics && Object.keys(compareData.metrics).length >= 2 && (
          <div>
            <h3 className="text-sm font-medium text-muted-foreground mb-1">指标对比</h3>
            {/* 实际对比周期提示 */}
            <p className="text-xs text-muted-foreground mb-2">
              {compareData.period_label}
              {(() => {
                const firstMetrics = Object.values(compareData.metrics)[0];
                if (!firstMetrics) return null;
                const years = firstMetrics.actual_years;
                const periodYears = period === "1y" ? 1 : period === "3y" ? 3 : period === "5y" ? 5 : null;
                if (period === "all" || (periodYears && years < periodYears * 0.9)) {
                  return <span className={period === "all" ? "ml-1" : "text-yellow-600 dark:text-yellow-400 ml-1"}>（实际 {years.toFixed(1)} 年）</span>;
                }
                return null;
              })()}
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-2 pr-2 text-muted-foreground font-medium"></th>
                    {selectedETFs.map((etf, i) => (
                      <th key={etf.code} className="text-right py-2 px-2 font-medium" style={{ color: LINE_COLORS[i] }}>
                        {etf.name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[
                    { key: "cagr", label: "CAGR", get: (code: string) => compareData.metrics[code]?.cagr ?? null, fmt: (v: number) => `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)}%`, color: (v: number) => v >= 0 ? "text-red-500" : "text-green-500" },
                    { key: "max_drawdown", label: "最大回撤", get: (code: string) => compareData.metrics[code]?.max_drawdown ?? null, fmt: (v: number) => `${(v * 100).toFixed(1)}%`, color: () => "text-green-500" },
                    { key: "volatility", label: "波动率", get: (code: string) => compareData.metrics[code]?.volatility ?? null, fmt: (v: number) => `${(v * 100).toFixed(1)}%`, color: () => "" },
                    { key: "temperature", label: "温度", get: (code: string) => compareData.temperatures?.[code]?.score ?? null, fmt: (v: number) => v.toFixed(0), color: (v: number) => v >= 70 ? "text-red-500" : v >= 40 ? "text-yellow-600" : "text-blue-500" },
                  ].map(row => (
                    <tr key={row.key} className="border-b border-border/50">
                      <td className="py-2 pr-2 text-muted-foreground">{row.label}</td>
                      {selectedETFs.map(etf => {
                        const val = row.get(etf.code);
                        return (
                          <td key={etf.code} className={cn("text-right py-2 px-2 font-mono", val != null ? row.color(val) : "")}>
                            {val != null ? row.fmt(val) : "-"}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// Suspense 边界（Next.js App Router 中 useSearchParams 需要）
export default function ComparePage() {
  return (
    <Suspense fallback={
      <div className="min-h-[100dvh] pb-20 bg-background flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    }>
      <CompareContent />
    </Suspense>
  );
}
