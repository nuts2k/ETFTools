import { useState, useEffect } from "react";
import { type ETFItem } from "@/lib/api";

const STORAGE_KEY = "etftool-watchlist";

export function useWatchlist() {
  const [watchlist, setWatchlist] = useState<ETFItem[]>([]);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        setWatchlist(JSON.parse(stored));
      }
    } catch (e) {
      console.error("Failed to load watchlist", e);
    } finally {
      setIsLoaded(true);
    }
  }, []);

  const save = (newList: ETFItem[]) => {
    setWatchlist(newList);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(newList));
  };

  const add = (item: ETFItem) => {
    if (watchlist.some((i) => i.code === item.code)) return;
    save([...watchlist, item]);
  };

  const remove = (code: string) => {
    save(watchlist.filter((i) => i.code !== code));
  };

  const isWatched = (code: string) => {
    return watchlist.some((i) => i.code === code);
  };

  return { watchlist, add, remove, isWatched, isLoaded };
}
