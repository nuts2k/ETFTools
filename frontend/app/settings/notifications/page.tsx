"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Bell, Eye, EyeOff, CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import {
  getTelegramConfig,
  saveTelegramConfig,
  testTelegramConfig,
  deleteTelegramConfig,
  type TelegramConfig
} from "@/lib/api";

export default function NotificationsPage() {
  const router = useRouter();
  const { token } = useAuth();
  const [mounted, setMounted] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [showToken, setShowToken] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);

  const [config, setConfig] = useState<TelegramConfig>({
    enabled: false,
    botToken: "",
    chatId: "",
    verified: false,
    lastTestAt: null,
  });

  // 标记 token 是否被用户修改过
  const [tokenModified, setTokenModified] = useState(false);

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
      const data = await getTelegramConfig(token!);
      // 确保所有字段都有默认值，避免 undefined
      setConfig({
        enabled: data.enabled ?? false,
        botToken: data.botToken ?? "",
        chatId: data.chatId ?? "",
        verified: data.verified ?? false,
        lastTestAt: data.lastTestAt ?? null,
      });
      // 重置修改标记
      setTokenModified(false);
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

  if (!mounted || isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-[100dvh] bg-background pb-20">
      {/* Header */}
      <header className="sticky top-0 z-40 bg-background/95 backdrop-blur-md pt-safe border-b border-border/50">
        <div className="flex h-14 items-center gap-4 px-5">
          <button onClick={() => router.back()} className="hover:opacity-70 transition-opacity">
            <ArrowLeft className="h-6 w-6" />
          </button>
          <h1 className="text-2xl font-bold tracking-tight">通知设置</h1>
        </div>
      </header>

      <main className="flex-1 w-full max-w-md mx-auto px-4 pt-6 space-y-6">
        {/* Telegram Bot Configuration Card */}
        <section>
          <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2 pl-3">
            Telegram 通知
          </h2>
          <div className="bg-card rounded-xl overflow-hidden shadow-sm ring-1 ring-border/50 divide-y divide-border/50">
            {/* Enable Toggle */}
            <div className="p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Bell className="h-5 w-5 text-muted-foreground" />
                <span className="text-base font-normal">启用通知</span>
              </div>
              <button
                onClick={() => setConfig({ ...config, enabled: !config.enabled })}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  config.enabled ? "bg-primary" : "bg-muted"
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    config.enabled ? "translate-x-6" : "translate-x-1"
                  }`}
                />
              </button>
            </div>

            {/* Bot Token Input */}
            <div className="p-4">
              <label className="block text-sm font-medium mb-2">Bot Token</label>
              <div className="relative">
                <input
                  type={showToken ? "text" : "password"}
                  value={config.botToken}
                  onChange={(e) => {
                    setConfig({ ...config, botToken: e.target.value });
                    setTokenModified(true);
                  }}
                  placeholder="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
                  className="w-full px-3 py-2 pr-10 bg-background border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                />
                <button
                  type="button"
                  onClick={() => setShowToken(!showToken)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showToken ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {/* Chat ID Input */}
            <div className="p-4">
              <label className="block text-sm font-medium mb-2">Chat ID</label>
              <input
                type="text"
                value={config.chatId}
                onChange={(e) => setConfig({ ...config, chatId: e.target.value })}
                placeholder="123456789"
                className="w-full px-3 py-2 bg-background border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>

            {/* Status Badge */}
            {config.verified && (
              <div className="p-4 flex items-center gap-2 bg-green-50 dark:bg-green-950/20">
                <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />
                <span className="text-sm text-green-600 dark:text-green-400">已验证</span>
                {config.lastTestAt && (
                  <span className="text-xs text-muted-foreground ml-auto">
                    最后测试: {new Date(config.lastTestAt).toLocaleString("zh-CN")}
                  </span>
                )}
              </div>
            )}
          </div>
        </section>

        {/* Action Buttons */}
        <section className="space-y-3">
          <button
            onClick={async () => {
              // 检查是否为已保存的标记且未修改
              const isSavedToken = config.botToken === "***SAVED***" && !tokenModified;

              if (!isSavedToken && !config.botToken) {
                showToast("请先填写 Bot Token", "error");
                return;
              }

              if (!config.chatId) {
                showToast("请先填写 Chat ID", "error");
                return;
              }

              setIsTesting(true);
              try {
                // 先保存配置
                await saveTelegramConfig(token!, {
                  enabled: config.enabled,
                  botToken: config.botToken,
                  chatId: config.chatId,
                });

                // 然后测试连接
                const result = await testTelegramConfig(token!);
                if (result.success) {
                  showToast("测试成功！请检查 Telegram 消息", "success");
                  await loadConfig();
                } else {
                  showToast(result.message || "测试失败", "error");
                }
              } catch (error: any) {
                showToast(error.message || "测试失败", "error");
              } finally {
                setIsTesting(false);
              }
            }}
            disabled={isTesting}
            className="w-full py-3 bg-primary text-primary-foreground rounded-lg font-medium hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {isTesting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                测试中...
              </>
            ) : (
              "测试连接"
            )}
          </button>

          <button
            onClick={async () => {
              // 检查是否为已保存的标记且未修改
              const isSavedToken = config.botToken === "***SAVED***" && !tokenModified;

              if (!isSavedToken && !config.botToken) {
                showToast("请先填写 Bot Token", "error");
                return;
              }

              if (!config.chatId) {
                showToast("请先填写 Chat ID", "error");
                return;
              }

              setIsSaving(true);
              try {
                await saveTelegramConfig(token!, {
                  enabled: config.enabled,
                  botToken: config.botToken,
                  chatId: config.chatId,
                });
                showToast("配置已保存", "success");
                await loadConfig();
              } catch (error: any) {
                showToast(error.message || "保存失败", "error");
              } finally {
                setIsSaving(false);
              }
            }}
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

          {config.botToken && (
            <button
              onClick={async () => {
                if (!confirm("确定要删除 Telegram 配置吗？")) return;
                try {
                  await deleteTelegramConfig(token!);
                  showToast("配置已删除", "success");
                  setConfig({
                    enabled: false,
                    botToken: "",
                    chatId: "",
                    verified: false,
                    lastTestAt: null,
                  });
                  setTokenModified(false);
                } catch (error: any) {
                  showToast(error.message || "删除失败", "error");
                }
              }}
              className="w-full py-3 bg-destructive/10 text-destructive rounded-lg font-medium hover:bg-destructive/20 transition-colors"
            >
              删除配置
            </button>
          )}
        </section>

        {/* Help Section */}
        <section>
          <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2 pl-3">
            配置说明
          </h2>
          <div className="bg-card rounded-xl overflow-hidden shadow-sm ring-1 ring-border/50 p-4 space-y-4">
            <div>
              <h3 className="font-medium mb-2">如何创建 Telegram Bot</h3>
              <ol className="text-sm text-muted-foreground space-y-1 list-decimal list-inside">
                <li>在 Telegram 中搜索 <code className="px-1 py-0.5 bg-muted rounded">@BotFather</code></li>
                <li>发送 <code className="px-1 py-0.5 bg-muted rounded">/newbot</code> 命令</li>
                <li>按提示设置 Bot 名称和用户名</li>
                <li>获取 Bot Token 并复制到上方输入框</li>
              </ol>
            </div>

            <div>
              <h3 className="font-medium mb-2">如何获取 Chat ID</h3>
              <ol className="text-sm text-muted-foreground space-y-1 list-decimal list-inside">
                <li>在 Telegram 中搜索 <code className="px-1 py-0.5 bg-muted rounded">@userinfobot</code></li>
                <li>启动对话，Bot 会返回你的 Chat ID</li>
                <li>复制 Chat ID 到上方输入框</li>
              </ol>
            </div>

            <div className="pt-2 border-t border-border/50">
              <p className="text-xs text-muted-foreground">
                💡 提示：Bot Token 将被加密存储，仅您可见。建议先测试连接确认配置正确。
              </p>
            </div>
          </div>
        </section>
      </main>

      {/* Toast Notification */}
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

