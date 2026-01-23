import { useState, useEffect } from "react";
import { type ETFItem, API_BASE_URL } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

const STORAGE_KEY = "etftool-watchlist";

export function useWatchlist() {
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
      } catch (e) {
        // Revert on error? For MVP we just log
        console.error("Cloud add failed", e);
      }
    } else {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(newList));
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

  return { watchlist, add, remove, reorder, isWatched, isLoaded };
}
