"use client";

import { useTheme } from "next-themes";
import { useSettings, type ColorMode, type RefreshRate } from "@/hooks/use-settings";
import { Moon, Sun, Monitor, Trash2, ChevronRight, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import { useState, useEffect } from "react";
import { ConfirmationDialog } from "@/components/ConfirmationDialog";
import { useAuth } from "@/lib/auth-context";
import Link from "next/link";

export default function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const { settings, updateSettings, isLoaded } = useSettings();
  const { user, logout } = useAuth();
  const [mounted, setMounted] = useState(false);
  const [cacheSize, setCacheSize] = useState("0 KB");
  const [showClearCacheDialog, setShowClearCacheDialog] = useState(false);

  // Prevent hydration mismatch
  useEffect(() => {
    setMounted(true);
    // Calculate rough local storage size
    let total = 0;
    if (typeof window !== "undefined") {
        for (const key in localStorage) {
        if (localStorage.hasOwnProperty(key)) {
            total += (localStorage[key].length + key.length) * 2;
        }
        }
    }
    setCacheSize((total / 1024).toFixed(2) + " KB");
  }, []);

  const handleClearCacheConfirm = () => {
    localStorage.clear();
    setShowClearCacheDialog(false);
    window.location.reload();
  };

  if (!mounted || !isLoaded) return null;

  return (
    <div className="flex flex-col min-h-[100dvh] bg-background pb-20">
      <header className="sticky top-0 z-40 bg-background/95 backdrop-blur-md pt-safe border-b border-border/50 transform-gpu backface-hidden">
        <div className="flex h-14 items-center justify-between px-5">
          <h1 className="text-2xl font-bold tracking-tight text-foreground">设置</h1>
        </div>
      </header>

      <main className="flex-1 w-full max-w-md mx-auto px-4 pt-6 space-y-6">
        
        {/* Account Section */}
        <section>
          <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2 pl-3">账号</h2>
          <div className="bg-card rounded-xl overflow-hidden shadow-sm ring-1 ring-border/50 divide-y divide-border/50">
            {user ? (
               <div className="p-4 flex items-center justify-between">
                 <div>
                   <p className="font-medium">{user.username}</p>
                   <p className="text-xs text-muted-foreground">已登录</p>
                 </div>
                 <div className="flex items-center gap-4">
                     <Link 
                        href="/settings/password"
                        className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
                     >
                        修改密码
                     </Link>
                     <button 
                       onClick={logout}
                       className="text-sm text-destructive font-medium hover:underline"
                     >
                       退出登录
                     </button>
                 </div>
               </div>
            ) : (
               <Link href="/login" className="flex items-center justify-between p-4 hover:bg-secondary/50 transition-colors">
                 <div>
                   <p className="font-medium">登录 / 注册</p>
                   <p className="text-xs text-muted-foreground">开启多设备同步</p>
                 </div>
                 <ChevronRight className="h-5 w-5 text-muted-foreground/50" />
               </Link>
            )}
          </div>
        </section>

        {/* General Settings */}
        <section>
          <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2 pl-3">通用设置</h2>
          <div className="bg-card rounded-xl overflow-hidden shadow-sm ring-1 ring-border/50 divide-y divide-border/50">
            
            {/* Refresh Rate */}
            <div className="group relative flex items-center justify-between p-4 min-h-[56px] cursor-pointer hover:bg-secondary/50 transition-colors">
              <div className="flex items-center gap-3">
                <span className="text-base font-normal">行情刷新频率</span>
              </div>
              <div className="flex items-center gap-1">
                <select 
                    className="appearance-none bg-transparent text-right text-muted-foreground text-sm focus:outline-none pr-6 cursor-pointer absolute inset-0 w-full h-full opacity-0"
                    value={settings.refreshRate}
                    onChange={(e) => updateSettings({ refreshRate: Number(e.target.value) as RefreshRate })}
                >
                    <option value={5}>每 5 秒</option>
                    <option value={10}>每 10 秒</option>
                    <option value={30}>每 30 秒</option>
                    <option value={0}>手动</option>
                </select>
                <span className="text-muted-foreground text-sm pointer-events-none">
                    {settings.refreshRate === 0 ? "手动" : `${settings.refreshRate}秒`}
                </span>
                <ChevronRight className="h-5 w-5 text-muted-foreground/50" />
              </div>
            </div>

            {/* Color Mode */}
            <div className="group relative flex items-center justify-between p-4 min-h-[56px] cursor-pointer hover:bg-secondary/50 transition-colors">
              <div className="flex items-center gap-3">
                <span className="text-base font-normal">涨跌颜色</span>
              </div>
              <div className="flex items-center gap-1">
                 <select 
                    className="appearance-none bg-transparent text-right text-muted-foreground text-sm focus:outline-none pr-6 cursor-pointer absolute inset-0 w-full h-full opacity-0"
                    value={settings.colorMode}
                    onChange={(e) => updateSettings({ colorMode: e.target.value as any })}
                >
                    <option value="red-up">红涨绿跌 (A股)</option>
                    <option value="green-up">绿涨红跌 (美股)</option>
                </select>
                <div className="flex gap-1 mr-2 pointer-events-none">
                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: settings.colorMode === "red-up" ? "#ef4444" : "#22c55e" }} />
                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: settings.colorMode === "red-up" ? "#22c55e" : "#ef4444" }} />
                </div>
                <span className="text-muted-foreground text-sm pointer-events-none">
                    {settings.colorMode === "red-up" ? "红涨绿跌" : "绿涨红跌"}
                </span>
                <ChevronRight className="h-5 w-5 text-muted-foreground/50" />
              </div>
            </div>

            {/* Theme Mode */}
            <div className="group relative flex items-center justify-between p-4 min-h-[56px] cursor-pointer hover:bg-secondary/50 transition-colors">
              <div className="flex items-center gap-3">
                <span className="text-base font-normal">主题模式</span>
              </div>
              <div className="flex items-center gap-1">
                <select 
                    className="appearance-none bg-transparent text-right text-muted-foreground text-sm focus:outline-none pr-6 cursor-pointer absolute inset-0 w-full h-full opacity-0"
                    value={theme}
                    onChange={(e) => setTheme(e.target.value)}
                >
                    <option value="system">跟随系统</option>
                    <option value="light">浅色模式</option>
                    <option value="dark">深色模式</option>
                </select>
                <span className="text-muted-foreground text-sm pointer-events-none">
                    {theme === 'system' ? '跟随系统' : theme === 'light' ? '浅色' : '深色'}
                </span>
                <ChevronRight className="h-5 w-5 text-muted-foreground/50" />
              </div>
            </div>

          </div>
        </section>

        {/* Data & Storage */}
        <section>
          <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2 pl-3">数据与存储</h2>
          <div className="bg-card rounded-xl overflow-hidden shadow-sm ring-1 ring-border/50 divide-y divide-border/50">
            <button 
                onClick={() => setShowClearCacheDialog(true)}
                className="w-full group relative flex items-center justify-between p-4 min-h-[56px] cursor-pointer hover:bg-destructive/5 transition-colors text-left"
            >
              <div className="flex items-center gap-3">
                <span className="text-base font-normal text-destructive">清除缓存</span>
              </div>
              <div className="flex items-center gap-1">
                <span className="text-muted-foreground text-sm">{cacheSize}</span>
                <ChevronRight className="h-5 w-5 text-muted-foreground/50" />
              </div>
            </button>
          </div>
        </section>

        <div className="py-8 text-center">
            <p className="text-xs text-muted-foreground/50">ETFTool v0.1.0 • Designed for Simplicity</p>
        </div>
      </main>

      <ConfirmationDialog 
        isOpen={showClearCacheDialog}
        title="清除缓存"
        description="确定要清除所有本地数据（包括自选列表和设置）吗？此操作无法撤销。"
        confirmLabel="确认清除"
        cancelLabel="取消"
        variant="destructive"
        onConfirm={handleClearCacheConfirm}
        onCancel={() => setShowClearCacheDialog(false)}
      />
    </div>
  );
}
