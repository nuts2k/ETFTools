"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { useAuth } from "@/lib/auth-context";
import { API_BASE_URL } from "@/lib/api";

export type ColorMode = "red-up" | "green-up";
export type RefreshRate = 15 | 30 | 60 | 0; // 0 = Manual

const VALID_REFRESH_RATES: number[] = [15, 30, 60, 0];
const SETTINGS_KEY = "etftool-settings";

interface Settings {
  colorMode: ColorMode;
  refreshRate: RefreshRate;
}

const DEFAULT_SETTINGS: Settings = {
  colorMode: "red-up",
  refreshRate: 30,
};

interface SettingsContextType {
  settings: Settings;
  updateSettings: (newSettings: Partial<Settings>) => Promise<void>;
  isLoaded: boolean;
}

const SettingsContext = createContext<SettingsContextType | undefined>(undefined);

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);
  const [isLoaded, setIsLoaded] = useState(false);
  const { user, token } = useAuth();

  // Load logic (Local vs Cloud)
  useEffect(() => {
    const sanitize = (raw: Settings): Settings => {
      const s = { ...raw };
      if (!VALID_REFRESH_RATES.includes(s.refreshRate)) {
        s.refreshRate = DEFAULT_SETTINGS.refreshRate;
      }
      return s;
    };

    if (user && user.settings) {
      // Merge cloud settings with defaults (to handle missing keys)
      setSettings(sanitize({ ...DEFAULT_SETTINGS, ...user.settings }));
      setIsLoaded(true);
    } else {
      // Local storage fallback
      try {
        const stored = localStorage.getItem(SETTINGS_KEY);
        if (stored) {
          setSettings(sanitize({ ...DEFAULT_SETTINGS, ...JSON.parse(stored) }));
        }
      } catch (e) {
        console.error("Failed to load settings", e);
      } finally {
        setIsLoaded(true);
      }
    }
  }, [user]);

  const updateSettings = async (newSettings: Partial<Settings>) => {
    const updated = { ...settings, ...newSettings };
    setSettings(updated);

    if (user && token) {
      try {
        await fetch(`${API_BASE_URL}/users/me/settings`, {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`
          },
          body: JSON.stringify(newSettings)
        });
      } catch (e) {
        console.error("Failed to sync settings", e);
      }
    } else {
      localStorage.setItem(SETTINGS_KEY, JSON.stringify(updated));
    }
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

  return (
    <SettingsContext.Provider value={{ settings, updateSettings, isLoaded }}>
      {children}
    </SettingsContext.Provider>
  );
}

export function useSettings() {
  const context = useContext(SettingsContext);
  if (context === undefined) {
    throw new Error("useSettings must be used within a SettingsProvider");
  }
  return context;
}
