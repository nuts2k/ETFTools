"use client";

import { useTheme } from "next-themes";
import { useSettings, type ColorMode, type RefreshRate } from "@/hooks/use-settings";
import { Moon, Sun, Monitor, Trash2, Check, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { useState, useEffect } from "react";

export default function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const { settings, updateSettings, isLoaded } = useSettings();
  const [mounted, setMounted] = useState(false);
  const [cacheSize, setCacheSize] = useState("0 KB");

  // Prevent hydration mismatch
  useEffect(() => {
    setMounted(true);
    // Calculate rough local storage size
    let total = 0;
    for (const key in localStorage) {
      if (localStorage.hasOwnProperty(key)) {
        total += (localStorage[key].length + key.length) * 2;
      }
    }
    setCacheSize((total / 1024).toFixed(2) + " KB");
  }, []);

  const clearCache = () => {
    if (confirm("确定要清除所有本地数据 (自选列表和设置) 吗？")) {
      localStorage.clear();
      window.location.reload();
    }
  };

  if (!mounted || !isLoaded) return null;

  return (
    <div className="flex flex-col min-h-screen bg-background pb-safe">
      <div className="sticky top-0 bg-background/95 backdrop-blur z-10 px-4 py-4 border-b">
        <h1 className="text-2xl font-bold">设置</h1>
      </div>

      <div className="px-4 py-6 space-y-8">
        {/* Appearance Section */}
        <Section title="外观">
          <div className="bg-card rounded-xl border shadow-sm divide-y">
            <div className="p-4 flex items-center justify-between">
              <span className="text-sm font-medium">主题</span>
              <div className="flex bg-secondary p-1 rounded-lg">
                <ThemeBtn active={theme === "light"} onClick={() => setTheme("light")} icon={Sun} />
                <ThemeBtn active={theme === "system"} onClick={() => setTheme("system")} icon={Monitor} />
                <ThemeBtn active={theme === "dark"} onClick={() => setTheme("dark")} icon={Moon} />
              </div>
            </div>
          </div>
        </Section>

        {/* Display Section */}
        <Section title="显示">
           <div className="bg-card rounded-xl border shadow-sm divide-y">
            <div className="p-4 flex flex-col gap-3">
              <span className="text-sm font-medium">涨跌颜色</span>
              <div className="grid grid-cols-2 gap-3">
                 <ColorModeBtn 
                    active={settings.colorMode === "red-up"} 
                    onClick={() => updateSettings({ colorMode: "red-up" })}
                    label="红涨 / 绿跌"
                    upColor="#ef4444"
                    downColor="#22c55e"
                 />
                 <ColorModeBtn 
                    active={settings.colorMode === "green-up"} 
                    onClick={() => updateSettings({ colorMode: "green-up" })}
                    label="绿涨 / 红跌"
                    upColor="#22c55e"
                    downColor="#ef4444"
                 />
              </div>
            </div>
           </div>
        </Section>

        {/* Data Section */}
        <Section title="数据刷新">
          <div className="bg-card rounded-xl border shadow-sm divide-y">
            <div className="p-4 flex items-center justify-between">
              <span className="text-sm font-medium">自动刷新</span>
              <select 
                className="bg-secondary text-sm rounded-md px-2 py-1 border-none focus:ring-1 focus:ring-primary"
                value={settings.refreshRate}
                onChange={(e) => updateSettings({ refreshRate: Number(e.target.value) as RefreshRate })}
              >
                <option value={5}>每 5 秒</option>
                <option value={10}>每 10 秒</option>
                <option value={30}>每 30 秒</option>
                <option value={0}>手动</option>
              </select>
            </div>
          </div>
        </Section>

        {/* Storage Section */}
        <Section title="存储">
           <div className="bg-card rounded-xl border shadow-sm divide-y">
             <button 
                onClick={clearCache}
                className="w-full p-4 flex items-center justify-between text-destructive hover:bg-destructive/5 transition-colors"
             >
               <div className="flex items-center gap-2">
                 <Trash2 className="h-4 w-4" />
                 <span className="text-sm font-medium">清除缓存</span>
               </div>
               <span className="text-xs text-muted-foreground">{cacheSize}</span>
             </button>
           </div>
        </Section>

        <div className="text-center pt-8 pb-4">
           <p className="text-xs text-muted-foreground">ETFTool v0.1.0 (MVP)</p>
        </div>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string, children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider ml-1">{title}</h3>
      {children}
    </div>
  );
}

function ThemeBtn({ active, onClick, icon: Icon }: any) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "p-2 rounded-md transition-all",
        active ? "bg-background shadow-sm text-foreground" : "text-muted-foreground hover:text-foreground"
      )}
    >
      <Icon className="h-4 w-4" />
    </button>
  );
}

function ColorModeBtn({ active, onClick, label, upColor, downColor }: any) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex flex-col items-center justify-center p-3 rounded-lg border-2 transition-all gap-2",
        active ? "border-primary bg-primary/5" : "border-transparent bg-secondary/50 hover:bg-secondary"
      )}
    >
      <div className="flex gap-1">
        <div className="w-3 h-3 rounded-full" style={{ backgroundColor: upColor }} />
        <div className="w-3 h-3 rounded-full" style={{ backgroundColor: downColor }} />
      </div>
      <span className={cn("text-[10px] font-medium", active ? "text-primary" : "text-muted-foreground")}>
        {label}
      </span>
    </button>
  );
}
