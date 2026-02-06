"use client"

import { useAuth } from "@/lib/auth-context"
import { useRouter } from "next/navigation"
import { useEffect, useState } from "react"
import { isAdmin } from "@/lib/admin-guard"
import { ArrowLeft, ChevronRight } from "lucide-react"
import { fetchSystemConfig, setRegistrationEnabled, setMaxWatchlistItems, type SystemConfig } from "@/lib/api"
import { useToast } from "@/components/Toast"
import { cn } from "@/lib/utils"

export default function SystemConfigPage() {
  const { user, token, isLoading } = useAuth()
  const router = useRouter()
  const { toast } = useToast()

  const [config, setConfig] = useState<SystemConfig | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!isLoading && !isAdmin(user)) router.push("/")
  }, [user, isLoading, router])

  useEffect(() => {
    if (!token || !isAdmin(user)) return
    fetchSystemConfig(token)
      .then(setConfig)
      .catch(() => toast("获取系统配置失败", "error"))
      .finally(() => setLoading(false))
  }, [token, user, toast])

  const handleToggleRegistration = async () => {
    if (!config || !token) return
    const prevConfig = { ...config }
    setConfig({ ...config, registration_enabled: !config.registration_enabled })
    try {
      await setRegistrationEnabled(token, !prevConfig.registration_enabled)
      toast(!prevConfig.registration_enabled ? "已开放注册" : "已关闭注册", "success")
    } catch (e) {
      setConfig(prevConfig)
      toast(e instanceof Error ? e.message : "操作失败", "error")
    }
  }

  const handleMaxWatchlistChange = async (value: number) => {
    if (!config || !token) return
    const prevConfig = { ...config }
    setConfig({ ...config, max_watchlist_items: value })
    try {
      await setMaxWatchlistItems(token, value)
      toast(`自选上限已设为 ${value}`, "success")
    } catch (e) {
      setConfig(prevConfig)
      toast(e instanceof Error ? e.message : "操作失败", "error")
    }
  }

  if (isLoading || !isAdmin(user)) return null

  return (
    <div className="flex flex-col min-h-[100dvh] bg-background pb-20">
      <header className="sticky top-0 z-40 bg-background/95 backdrop-blur-md pt-safe border-b border-border/50 transform-gpu backface-hidden">
        <div className="flex h-14 items-center px-5 gap-3">
          <button onClick={() => router.push("/admin")} className="p-1 -ml-1">
            <ArrowLeft className="h-5 w-5 text-foreground" />
          </button>
          <h1 className="text-lg font-semibold text-foreground">系统设置</h1>
        </div>
      </header>

      <main className="flex-1 w-full max-w-md mx-auto px-4 pt-6 space-y-6">
        {loading ? null : config && (
          <>
            {/* Registration Control */}
            <section>
              <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2 pl-3">注册控制</h2>
              <div className="bg-card rounded-xl overflow-hidden ring-1 ring-border/50">
                <div className="flex items-center justify-between p-4 min-h-[56px]">
                  <span className="text-base font-normal">开放注册</span>
                  <button
                    onClick={handleToggleRegistration}
                    className={cn(
                      "relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200",
                      config.registration_enabled ? "bg-primary" : "bg-muted"
                    )}
                  >
                    <span className={cn(
                      "inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform duration-200",
                      config.registration_enabled ? "translate-x-6" : "translate-x-1"
                    )} />
                  </button>
                </div>
              </div>
            </section>

            {/* Limits */}
            <section>
              <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2 pl-3">限制</h2>
              <div className="bg-card rounded-xl overflow-hidden ring-1 ring-border/50">
                <div className="group relative flex items-center justify-between p-4 min-h-[56px] cursor-pointer hover:bg-secondary/50 transition-colors">
                  <span className="text-base font-normal">自选上限</span>
                  <div className="flex items-center gap-1">
                    <select
                      className="appearance-none bg-transparent text-right text-muted-foreground text-sm focus:outline-none pr-6 cursor-pointer absolute inset-0 w-full h-full opacity-0"
                      value={config.max_watchlist_items}
                      onChange={(e) => handleMaxWatchlistChange(Number(e.target.value))}
                    >
                      <option value={50}>50</option>
                      <option value={100}>100</option>
                      <option value={200}>200</option>
                      <option value={500}>500</option>
                    </select>
                    <span className="text-muted-foreground text-sm pointer-events-none">
                      {config.max_watchlist_items}
                    </span>
                    <ChevronRight className="h-5 w-5 text-muted-foreground/50" />
                  </div>
                </div>
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  )
}
