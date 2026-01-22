import { useState, useEffect } from "react";
import { type ETFItem } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

const STORAGE_KEY = "etftool-watchlist";

export function useWatchlist() {
  const [watchlist, setWatchlist] = useState<ETFItem[]>([]);
  const [isLoaded, setIsLoaded] = useState(false);
  const { user, token } = useAuth();

  // Load watchlist (Local or Cloud)
  useEffect(() => {
    const load = async () => {
      if (user && token) {
        // Cloud mode
        try {
          const res = await fetch("http://localhost:8000/api/v1/watchlist/", {
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
  }, [user, token]);

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
              await fetch("http://localhost:8000/api/v1/watchlist/sync", {
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
              const res = await fetch("http://localhost:8000/api/v1/watchlist/", {
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
    // Optimistic update
    const newList = [...watchlist, item];
    if (watchlist.some((i) => i.code === item.code)) return;
    setWatchlist(newList);

    if (user && token) {
      try {
        await fetch(`http://localhost:8000/api/v1/watchlist/${item.code}`, {
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
        await fetch(`http://localhost:8000/api/v1/watchlist/${code}`, {
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

  const isWatched = (code: string) => {
    return watchlist.some((i) => i.code === code);
  };

  return { watchlist, add, remove, isWatched, isLoaded };
}
