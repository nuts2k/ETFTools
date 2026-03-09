"use client"

import { useState, useEffect, useCallback } from "react"
import { Loader2, Trash2, Bell } from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import {
  getPriceAlerts,
  deletePriceAlert,
  getTelegramConfig,
  type PriceAlertItem,
} from "@/lib/api"
import { cn } from "@/lib/utils"
import { useRouter } from "next/navigation"

const MAX_ACTIVE_ALERTS = 20

export default function PriceAlertList() {
  const { token } = useAuth()
  const router = useRouter()
  const [alerts, setAlerts] = useState<PriceAlertItem[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<"active" | "triggered">("active")
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [telegramConfigured, setTelegramConfigured] = useState<boolean | null>(null)

  const fetchAlerts = useCallback(async () => {
    if (!token) return
    try {
      setLoading(true)
      const [alertsData, telegramData] = await Promise.all([
        getPriceAlerts(token),
        getTelegramConfig(token).catch(() => null),
      ])
      setAlerts(alertsData)
      setTelegramConfigured(
        !!telegramData?.enabled && !!telegramData?.verified
      )
    } catch {
      // 静默失败
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    fetchAlerts()
  }, [fetchAlerts])

  const handleDelete = async (id: number) => {
    if (confirmDeleteId !== id) {
      setConfirmDeleteId(id)
      return
    }
    if (!token) return
    setDeletingId(id)
    setConfirmDeleteId(null)
    setDeleteError(null)
    try {
      await deletePriceAlert(token, id)
      setAlerts((prev) => prev.filter((a) => a.id !== id))
    } catch {
      setDeleteError("删除失败，请重试")
    } finally {
      setDeletingId(null)
    }
  }

  // 点击其他地方时取消确认状态
  useEffect(() => {
    if (confirmDeleteId === null) return
    const timer = setTimeout(() => setConfirmDeleteId(null), 3000)
    return () => clearTimeout(timer)
  }, [confirmDeleteId])

  const activeAlerts = alerts.filter((a) => !a.is_triggered)
  const triggeredAlerts = alerts.filter((a) => a.is_triggered)
  const displayed = filter === "active" ? activeAlerts : triggeredAlerts

  if (!token) return null

  return (
    <section>
      {/* 标题 */}
      <div className="flex items-center gap-2 mb-2 pl-3">
        <Bell className="h-4 w-4 text-primary" />
        <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          到价提醒
          <span className="ml-1.5 normal-case">
            ({activeAlerts.length}/{MAX_ACTIVE_ALERTS})
          </span>
        </h2>
      </div>

      <div className="bg-card rounded-xl overflow-hidden shadow-sm ring-1 ring-border/50 p-4">
        {/* 删除错误提示 */}
        {deleteError && (
          <div className="p-3 bg-destructive/10 rounded-lg text-sm text-destructive mb-3">
            {deleteError}
          </div>
        )}

        {/* Telegram 未配置提示 */}
        {telegramConfigured === false && (
          <div className="p-3 bg-amber-500/10 rounded-lg text-sm mb-3">
            <p className="text-amber-600 dark:text-amber-400">
              请先配置 Telegram 通知才能创建到价提醒
            </p>
            <button
              onClick={() => router.push("/settings/notifications")}
              className="mt-1 text-primary font-medium text-sm underline"
            >
              去配置
            </button>
          </div>
        )}

        {/* 筛选标签 */}
        <div className="flex gap-2 mb-3">
          <button
            onClick={() => setFilter("active")}
            className={cn(
              "px-3 py-1 rounded-full text-sm font-medium transition-colors",
              filter === "active"
                ? "bg-primary text-primary-foreground"
                : "bg-secondary text-muted-foreground"
            )}
          >
            活跃 ({activeAlerts.length})
          </button>
          <button
            onClick={() => setFilter("triggered")}
            className={cn(
              "px-3 py-1 rounded-full text-sm font-medium transition-colors",
              filter === "triggered"
                ? "bg-primary text-primary-foreground"
                : "bg-secondary text-muted-foreground"
            )}
          >
            已触发 ({triggeredAlerts.length})
          </button>
        </div>

        {/* 列表 */}
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : displayed.length === 0 ? (
          <div className="text-center py-8 text-sm text-muted-foreground">
            {filter === "active" ? "暂无活跃提醒" : "暂无已触发提醒"}
          </div>
        ) : (
          <div className="space-y-2">
            {displayed.map((alert) => (
              <div
                key={alert.id}
                className="p-3 bg-secondary/50 rounded-lg"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      {alert.is_triggered && (
                        <span className="text-green-500 text-xs font-medium">
                          ✅
                        </span>
                      )}
                      <span className="font-medium text-sm truncate">
                        {alert.etf_name}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        ({alert.etf_code})
                      </span>
                    </div>

                    <div className="mt-1 text-sm">
                      <span>
                        {alert.direction === "below" ? "⬇️ 跌破" : "⬆️ 突破"}{" "}
                        {alert.target_price}
                      </span>
                      {alert.is_triggered && alert.triggered_price && (
                        <span className="ml-2 text-muted-foreground">
                          → 实际 {alert.triggered_price}
                        </span>
                      )}
                    </div>

                    {alert.note && (
                      <div className="mt-1 text-xs text-muted-foreground truncate">
                        📝 {alert.note}
                      </div>
                    )}

                    <div className="mt-1 text-xs text-muted-foreground/60">
                      {alert.is_triggered && alert.triggered_at
                        ? `触发于 ${new Date(alert.triggered_at).toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" })} ${new Date(alert.triggered_at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}`
                        : `设置于 ${new Date(alert.created_at).toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" })}`}
                    </div>
                  </div>

                  <button
                    onClick={() => handleDelete(alert.id)}
                    disabled={deletingId === alert.id}
                    className={cn(
                      "ml-2 p-2 rounded-lg transition-colors",
                      confirmDeleteId === alert.id
                        ? "bg-destructive/15 text-destructive"
                        : "hover:bg-destructive/10 text-muted-foreground hover:text-destructive"
                    )}
                  >
                    {deletingId === alert.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : confirmDeleteId === alert.id ? (
                      <span className="text-xs font-medium px-1">确认</span>
                    ) : (
                      <Trash2 className="h-4 w-4" />
                    )}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
