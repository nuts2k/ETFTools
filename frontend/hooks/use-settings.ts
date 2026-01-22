import { useState, useEffect } from "react";

export type ColorMode = "red-up" | "green-up";
export type RefreshRate = 5 | 10 | 30 | 0; // 0 = Manual

const SETTINGS_KEY = "etftool-settings";

interface Settings {
  colorMode: ColorMode;
  refreshRate: RefreshRate;
}

const DEFAULT_SETTINGS: Settings = {
  colorMode: "red-up",
  refreshRate: 5,
};

export function useSettings() {
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);
  const [isLoaded, setIsLoaded] = useState(false);

  // Load from local storage
  useEffect(() => {
    try {
      const stored = localStorage.getItem(SETTINGS_KEY);
      if (stored) {
        setSettings({ ...DEFAULT_SETTINGS, ...JSON.parse(stored) });
      }
    } catch (e) {
      console.error("Failed to load settings", e);
    } finally {
      setIsLoaded(true);
    }
  }, []);

  // Save to local storage
  const updateSettings = (newSettings: Partial<Settings>) => {
    const updated = { ...settings, ...newSettings };
    setSettings(updated);
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(updated));
  };

  // Apply CSS variables for colors
  useEffect(() => {
    const root = document.documentElement;
    if (settings.colorMode === "red-up") {
      // Red Up (#ef4444), Green Down (#22c55e)
      root.style.setProperty("--up", "#ef4444");
      root.style.setProperty("--down", "#22c55e");
    } else {
      // Green Up (#22c55e), Red Down (#ef4444)
      root.style.setProperty("--up", "#22c55e");
      root.style.setProperty("--down", "#ef4444");
    }
  }, [settings.colorMode]);

  return {
    settings,
    updateSettings,
    isLoaded
  };
}
