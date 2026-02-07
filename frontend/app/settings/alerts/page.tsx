"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Bell,
  Thermometer,
  TrendingUp,
  BarChart3,
  Calendar,
  CheckCircle2,
  XCircle,
  Loader2,
} from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import {
  getAlertConfig,
  saveAlertConfig,
  triggerAlertCheck,
  getTelegramConfig,
  type AlertConfig,
} from "@/lib/api";

export default function AlertsSettingsPage() {
  const router = useRouter();
  const { token } = useAuth();
  const [mounted, setMounted] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [telegramVerified, setTelegramVerified] = useState(false);
  const [toast, setToast] = useState<{
    message: string;
    type: "success" | "error";
  } | null>(null);

  const [config, setConfig] = useState<AlertConfig>({
    enabled: true,
    temperature_change: true,
    extreme_temperature: true,
    rsi_signal: true,
    ma_crossover: true,
    ma_alignment: true,
    weekly_signal: true,
    daily_summary: true,
    max_alerts_per_day: 20,
  });

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (mounted && token) {
      loadConfig();
    }
  }, [mounted, token]);

  const loadConfig = async () => {
    try {
      const [alertData, telegramData] = await Promise.all([
        getAlertConfig(token!),
        getTelegramConfig(token!).catch(() => null),
      ]);
      setConfig(alertData);
      setTelegramVerified(
        !!telegramData?.enabled && !!telegramData?.verified
      );
    } catch (error) {
      console.error("Failed to load config:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const showToast = (message: string, type: "success" | "error") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await saveAlertConfig(token!, config);
      showToast("配置已保存", "success");
    } catch (error: any) {
      showToast(error.message || "保存失败", "error");
    } finally {
      setIsSaving(false);
    }
  };

  const handleTest = async () => {
    setIsTesting(true);
    try {
      await saveAlertConfig(token!, config);
      const result = await triggerAlertCheck(token!);
      if (result.success) {
        showToast("检查完成，如有信号将发送通知", "success");
      } else {
        showToast(result.message || "检查失败", "error");
      }
    } catch (error: any) {
      showToast(error.message || "检查失败", "error");
    } finally {
      setIsTesting(false);
    }
  };

  if (!mounted || isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const Toggle = ({
    checked,
    onChange,
    disabled,
  }: {
    checked: boolean;
    onChange: (v: boolean) => void;
    disabled?: boolean;
  }) => (
    <button
      onClick={() => !disabled && onChange(!checked)}
      disabled={disabled}
      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
        disabled ? "bg-muted opacity-50 cursor-not-allowed" : checked ? "bg-primary" : "bg-muted"
      }`}
    >
      <span
        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
          checked ? "translate-x-6" : "translate-x-1"
        }`}
      />
    </button>
  );

  return (
    <div className="flex flex-col min-h-[100dvh] bg-background pb-20">
      {/* Header */}
      <header className="sticky top-0 z-40 bg-background/95 backdrop-blur-md pt-safe border-b border-border/50">
        <div className="flex h-14 items-center gap-4 px-5">
          <button
            onClick={() => router.back()}
            className="hover:opacity-70 transition-opacity"
          >
            <ArrowLeft className="h-6 w-6" />
          </button>
          <h1 className="text-2xl font-bold tracking-tight">信号通知</h1>
        </div>
      </header>

      <main className="flex-1 w-full max-w-md mx-auto px-4 pt-6 space-y-6">
        {/* 主开关 */}
        <section>
          <div className="bg-card rounded-xl overflow-hidden shadow-sm ring-1 ring-border/50">
            <div className="p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Bell className="h-5 w-5 text-muted-foreground" />
                <span className="text-base font-medium">启用信号通知</span>
              </div>
              <Toggle
                checked={config.enabled}
                onChange={(v) => setConfig({ ...config, enabled: v })}
              />
            </div>
          </div>
        </section>

        {/* 每日摘要 */}
        <section>
          <div className="bg-card rounded-xl overflow-hidden shadow-sm ring-1 ring-border/50">
            <div className="p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Calendar className="h-5 w-5 text-muted-foreground" />
                <div>
                  <span className="text-base font-medium">每日市场摘要</span>
                  <p className="text-xs text-muted-foreground">
                    {telegramVerified
                      ? "收盘后推送自选日报"
                      : "请先配置并验证 Telegram Bot"}
                  </p>
                </div>
              </div>
              <Toggle
                checked={config.daily_summary}
                disabled={!telegramVerified}
                onChange={(v) =>
                  setConfig({ ...config, daily_summary: v })
                }
              />
            </div>
          </div>
        </section>

        {/* 信号类型 */}
        <section>
          <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2 pl-3">
            监控信号类型
          </h2>
          <div className="bg-card rounded-xl overflow-hidden shadow-sm ring-1 ring-border/50 divide-y divide-border/50">
            <div className="p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Thermometer className="h-5 w-5 text-orange-500" />
                <div>
                  <span className="text-base">温度等级变化</span>
                  <p className="text-xs text-muted-foreground">
                    如 cool → warm
                  </p>
                </div>
              </div>
              <Toggle
                checked={config.temperature_change}
                onChange={(v) =>
                  setConfig({ ...config, temperature_change: v })
                }
              />
            </div>

            <div className="p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Thermometer className="h-5 w-5 text-red-500" />
                <div>
                  <span className="text-base">极端温度</span>
                  <p className="text-xs text-muted-foreground">
                    freezing 或 hot
                  </p>
                </div>
              </div>
              <Toggle
                checked={config.extreme_temperature}
                onChange={(v) =>
                  setConfig({ ...config, extreme_temperature: v })
                }
              />
            </div>

            <div className="p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <BarChart3 className="h-5 w-5 text-cyan-500" />
                <div>
                  <span className="text-base">RSI 超买超卖</span>
                  <p className="text-xs text-muted-foreground">
                    RSI &gt; 70 或 &lt; 30
                  </p>
                </div>
              </div>
              <Toggle
                checked={config.rsi_signal}
                onChange={(v) => setConfig({ ...config, rsi_signal: v })}
              />
            </div>

            <div className="p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <TrendingUp className="h-5 w-5 text-blue-500" />
                <div>
                  <span className="text-base">均线突破</span>
                  <p className="text-xs text-muted-foreground">
                    上穿/下穿 MA20、MA60
                  </p>
                </div>
              </div>
              <Toggle
                checked={config.ma_crossover}
                onChange={(v) => setConfig({ ...config, ma_crossover: v })}
              />
            </div>

            <div className="p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <BarChart3 className="h-5 w-5 text-purple-500" />
                <div>
                  <span className="text-base">均线排列变化</span>
                  <p className="text-xs text-muted-foreground">
                    多头/空头排列形成
                  </p>
                </div>
              </div>
              <Toggle
                checked={config.ma_alignment}
                onChange={(v) => setConfig({ ...config, ma_alignment: v })}
              />
            </div>

            <div className="p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Calendar className="h-5 w-5 text-green-500" />
                <div>
                  <span className="text-base">周线趋势信号</span>
                  <p className="text-xs text-muted-foreground">
                    周线多空转换
                  </p>
                </div>
              </div>
              <Toggle
                checked={config.weekly_signal}
                onChange={(v) => setConfig({ ...config, weekly_signal: v })}
              />
            </div>
          </div>
        </section>

        {/* 操作按钮 */}
        <section className="space-y-3">
          <button
            onClick={handleTest}
            disabled={isTesting}
            className="w-full py-3 bg-primary text-primary-foreground rounded-lg font-medium hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {isTesting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                检查中...
              </>
            ) : (
              "立即检查"
            )}
          </button>

          <button
            onClick={handleSave}
            disabled={isSaving}
            className="w-full py-3 bg-secondary text-secondary-foreground rounded-lg font-medium hover:bg-secondary/80 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {isSaving ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                保存中...
              </>
            ) : (
              "保存配置"
            )}
          </button>
        </section>

        {/* 说明 */}
        <section>
          <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2 pl-3">
            说明
          </h2>
          <div className="bg-card rounded-xl overflow-hidden shadow-sm ring-1 ring-border/50 p-4 space-y-2">
            <p className="text-sm text-muted-foreground">
              系统将在每个交易日收盘后（15:30）自动检查您自选股的指标变化，并通过
              Telegram 发送通知。
            </p>
            <p className="text-sm text-muted-foreground">
              同一 ETF 的同类信号每天最多发送一次，避免重复打扰。
            </p>
            <p className="text-xs text-muted-foreground mt-2">
              💡 请先在「通知设置」中配置并验证 Telegram Bot
            </p>
          </div>
        </section>
      </main>

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-24 left-1/2 -translate-x-1/2 z-50 animate-in fade-in slide-in-from-bottom-2">
          <div
            className={`flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg ${
              toast.type === "success"
                ? "bg-green-600 text-white"
                : "bg-destructive text-destructive-foreground"
            }`}
          >
            {toast.type === "success" ? (
              <CheckCircle2 className="h-4 w-4" />
            ) : (
              <XCircle className="h-4 w-4" />
            )}
            <span className="text-sm font-medium">{toast.message}</span>
          </div>
        </div>
      )}
    </div>
  );
}
