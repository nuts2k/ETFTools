"use client";

import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { type ETFItem, type ETFDetail, type ETFMetrics, API_BASE_URL, fetchClient } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

const STORAGE_KEY = "etftool-watchlist";

interface WatchlistContextType {
  watchlist: ETFItem[];
  add: (item: ETFItem) => Promise<void>;
  remove: (code: string) => Promise<void>;
  reorder: (newOrderCodes: string[]) => Promise<void>;
  isWatched: (code: string) => boolean;
  isLoaded: boolean;
  refresh: () => Promise<void>;
}

const WatchlistContext = createContext<WatchlistContextType | undefined>(undefined);

export function WatchlistProvider({ children }: { children: ReactNode }) {
  const [watchlist, setWatchlist] = useState<ETFItem[]>([]);
  const [isLoaded, setIsLoaded] = useState(false);
  const { user, token, isLoading: authLoading } = useAuth();

  // Load watchlist (Local or Cloud)
  useEffect(() => {
    // 如果认证状态还在加载中，不要急着做决定
    if (authLoading) return;

    const load = async () => {
      if (user && token) {
        // Cloud mode
        try {
          const res = await fetch(`${API_BASE_URL}/watchlist/`, {
            headers: { Authorization: `Bearer ${token}` }
          });
          if (res.ok) {
            const data = await res.json();
            setWatchlist(data);
          }
        } catch (e) {
          console.error("Failed to fetch cloud watchlist", e);
        }
      } else {
        // Local mode
        try {
          const stored = localStorage.getItem(STORAGE_KEY);
          if (stored) {
            setWatchlist(JSON.parse(stored));
          }
        } catch (e) {
          console.error("Failed to load local watchlist", e);
        }
      }
      setIsLoaded(true);
    };

    load();
  }, [user, token, authLoading]);

  // Sync logic when logging in
  useEffect(() => {
    const sync = async () => {
      if (user && token && isLoaded) {
        // Check if there are local items to sync
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) {
          const localItems: ETFItem[] = JSON.parse(stored);
          if (localItems.length > 0) {
            try {
              await fetch(`${API_BASE_URL}/watchlist/sync`, {
                method: "POST",
                headers: {
                  "Content-Type": "application/json",
                  Authorization: `Bearer ${token}`
                },
                body: JSON.stringify(localItems)
              });
              // Clear local storage after sync
              localStorage.removeItem(STORAGE_KEY);
              // Refresh list
              const res = await fetch(`${API_BASE_URL}/watchlist/`, {
                headers: { Authorization: `Bearer ${token}` }
              });
              if (res.ok) {
                const data = await res.json();
                setWatchlist(data);
              }
            } catch (e) {
              console.error("Sync failed", e);
            }
          }
        }
      }
    };
    
    // Only run once when user becomes available
    if (user && isLoaded) {
        sync();
    }
  }, [user, token, isLoaded]);


  const fetchMetricsForItem = async (code: string): Promise<Partial<ETFItem> | null> => {
    try {
      const [infoResult, metricsResult] = await Promise.allSettled([
        fetchClient<ETFDetail>(`/etf/${code}/info`),
        fetchClient<ETFMetrics>(`/etf/${code}/metrics?period=5y`),
      ]);
      const info = infoResult.status === "fulfilled" ? infoResult.value : null;
      const metrics = metricsResult.status === "fulfilled" ? metricsResult.value : null;
      return {
        ...(info && { price: info.price, change_pct: info.change_pct }),
        ...(metrics && {
          atr: metrics.atr,
          current_drawdown: metrics.current_drawdown,
          weekly_direction: metrics.weekly_trend?.direction,
          consecutive_weeks: metrics.weekly_trend?.consecutive_weeks,
          temperature_score: metrics.temperature?.score,
          temperature_level: metrics.temperature?.level,
        }),
      };
    } catch {
      return null;
    }
  };

  const add = async (item: ETFItem) => {
    if (watchlist.some((i) => i.code === item.code)) return;
    
    // Optimistic update - Add to TOP
    const newList = [item, ...watchlist];
    setWatchlist(newList);

    if (user && token) {
      try {
        await fetch(`${API_BASE_URL}/watchlist/${item.code}`, {
          method: "POST",
          headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`
          },
          body: JSON.stringify(item)
        });
        // POST 成功后，重新获取完整列表（含指标）
        const res = await fetch(`${API_BASE_URL}/watchlist/`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (res.ok) {
          const data = await res.json();
          setWatchlist(data);
        }
      } catch (e) {
        console.error("Cloud add failed", e);
      }
    } else {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(newList));
      // 异步补全指标（不阻塞 add 操作）
      fetchMetricsForItem(item.code).then((enriched) => {
        if (enriched) {
          setWatchlist(prev => {
            const updated = prev.map(i => i.code === item.code ? { ...i, ...enriched } : i);
            localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
            return updated;
          });
        }
      });
    }
  };

  const remove = async (code: string) => {
    const newList = watchlist.filter((i) => i.code !== code);
    setWatchlist(newList);

    if (user && token) {
      try {
        await fetch(`${API_BASE_URL}/watchlist/${code}`, {
          method: "DELETE",
          headers: { Authorization: `Bearer ${token}` }
        });
      } catch (e) {
        console.error("Cloud remove failed", e);
      }
    } else {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(newList));
    }
  };

  const reorder = async (newOrderCodes: string[]) => {
    // 1. Construct new list based on codes
    const itemMap = new Map(watchlist.map(item => [item.code, item]));
    const newList = newOrderCodes
      .map(code => itemMap.get(code))
      .filter((item): item is ETFItem => item !== undefined);
    
    // If somehow items are missing (shouldn't happen), append them at end
    const missingItems = watchlist.filter(item => !newOrderCodes.includes(item.code));
    const finalList = [...newList, ...missingItems];

    setWatchlist(finalList);

    if (user && token) {
      try {
        await fetch(`${API_BASE_URL}/watchlist/reorder`, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${token}`
            },
            body: JSON.stringify(newOrderCodes)
        });
      } catch (e) {
        console.error("Cloud reorder failed", e);
      }
    } else {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(finalList));
    }
  };

  const isWatched = (code: string) => {
    return watchlist.some((i) => i.code === code);
  };

  const refresh = async () => {
    if (user && token) {
      try {
        const res = await fetch(`${API_BASE_URL}/watchlist/`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (res.ok) {
          const data = await res.json();
          setWatchlist(data);
        }
      } catch (e) {
        console.error("Refresh failed", e);
      }
    } else {
      await refreshLocal();
    }
  };

  const refreshLocal = async () => {
    const currentList = [...watchlist];
    if (currentList.length === 0) return;

    const results = await Promise.allSettled(
      currentList.map(async (item) => {
        const [infoResult, metricsResult] = await Promise.allSettled([
          fetchClient<ETFDetail>(`/etf/${item.code}/info`),
          fetchClient<ETFMetrics>(`/etf/${item.code}/metrics?period=5y`),
        ]);
        const info = infoResult.status === "fulfilled" ? infoResult.value : null;
        const metrics = metricsResult.status === "fulfilled" ? metricsResult.value : null;
        return {
          ...item,
          price: info?.price ?? item.price,
          change_pct: info?.change_pct ?? item.change_pct,
          atr: metrics?.atr ?? item.atr,
          current_drawdown: metrics?.current_drawdown ?? item.current_drawdown,
          weekly_direction: metrics?.weekly_trend?.direction ?? item.weekly_direction,
          consecutive_weeks: metrics?.weekly_trend?.consecutive_weeks ?? item.consecutive_weeks,
          temperature_score: metrics?.temperature?.score ?? item.temperature_score,
          temperature_level: metrics?.temperature?.level ?? item.temperature_level,
        };
      })
    );

    const newList = results.map((result, i) =>
      result.status === "fulfilled" ? result.value : currentList[i]
    );
    setWatchlist(newList);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(newList));
  };

  return (
    <WatchlistContext.Provider value={{ watchlist, add, remove, reorder, isWatched, isLoaded, refresh }}>
      {children}
    </WatchlistContext.Provider>
  );
}

export function useWatchlist() {
  const context = useContext(WatchlistContext);
  if (context === undefined) {
    throw new Error("useWatchlist must be used within a WatchlistProvider");
  }
  return context;
}
