"use client"

import { useState, useEffect } from "react"
import { Bell, X, Loader2 } from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import { getTelegramConfig, createPriceAlert, getPriceAlerts } from "@/lib/api"
import { cn } from "@/lib/utils"
import { useRouter } from "next/navigation"

interface PriceAlertButtonProps {
  etfCode: string
  etfName: string
  currentPrice: number
}

export default function PriceAlertButton({
  etfCode,
  etfName,
  currentPrice,
}: PriceAlertButtonProps) {
  const { token } = useAuth()
  const router = useRouter()
  const [showDialog, setShowDialog] = useState(false)
  const [hasActiveAlert, setHasActiveAlert] = useState(false)
  const [targetPrice, setTargetPrice] = useState("")
  const [direction, setDirection] = useState<"above" | "below">("below")
  const [note, setNote] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState("")
  const [successMsg, setSuccessMsg] = useState("")
  const [telegramConfigured, setTelegramConfigured] = useState<boolean | null>(null)

  // 组件挂载时获取活跃提醒和 Telegram 配置（缓存，避免每次点击都请求）
  useEffect(() => {
    if (!token) return
    Promise.all([
      getPriceAlerts(token, true),
      getTelegramConfig(token).catch(() => null),
    ])
      .then(([alerts, telegramData]) => {
        const has = alerts.some((a) => a.etf_code === etfCode)
        setHasActiveAlert(has)
        setTelegramConfigured(
          !!telegramData?.enabled && !!telegramData?.verified
        )
      })
      .catch(() => {})
  }, [token, etfCode])

  const handleBellClick = async () => {
    if (!token) {
      router.push("/login")
      return
    }

    // 使用已缓存的 Telegram 配置状态
    if (telegramConfigured === false) {
      setError("请先配置并验证 Telegram 通知")
      setShowDialog(true)
      return
    }

    setError("")
    setSuccessMsg("")
    setTargetPrice("")
    setNote("")
    setShowDialog(true)
  }

  // 目标价变化时自动推断方向
  useEffect(() => {
    const price = parseFloat(targetPrice)
    if (!isNaN(price) && price > 0 && currentPrice > 0) {
      setDirection(price < currentPrice ? "below" : "above")
    }
  }, [targetPrice, currentPrice])

  const handleSubmit = async () => {
    const price = parseFloat(targetPrice)
    if (isNaN(price) || price <= 0) {
      setError("请输入有效的目标价格")
      return
    }

    setIsSubmitting(true)
    setError("")
    try {
      await createPriceAlert(token!, {
        etf_code: etfCode,
        etf_name: etfName,
        target_price: price,
        direction,
        note: note.trim() || undefined,
      })
      setSuccessMsg("提醒设置成功")
      setHasActiveAlert(true)
      setTimeout(() => setShowDialog(false), 1200)
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "创建失败"
      setError(message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <>
      <button
        onClick={handleBellClick}
        className="flex w-10 h-10 items-center justify-center rounded-full text-foreground hover:bg-secondary transition-colors active:scale-90"
      >
        <Bell
          className={cn(
            "h-5 w-5 transition-all",
            hasActiveAlert
              ? "fill-primary text-primary"
              : "text-muted-foreground"
          )}
        />
      </button>

      {/* 创建弹窗 */}
      {showDialog && (
        <div className="fixed inset-0 z-[100] flex items-end sm:items-center justify-center">
          {/* 遮罩 */}
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => !isSubmitting && setShowDialog(false)}
          />

          {/* 弹窗内容 */}
          <div className="relative w-full max-w-md bg-background rounded-t-2xl sm:rounded-2xl p-6 pb-safe animate-in slide-in-from-bottom duration-200">
            {/* 标题栏 */}
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold">设置到价提醒</h3>
              <button
                onClick={() => !isSubmitting && setShowDialog(false)}
                className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-secondary"
              >
                <X className="h-5 w-5 text-muted-foreground" />
              </button>
            </div>

            {/* ETF 信息 */}
            <div className="mb-4 text-sm text-muted-foreground">
              <span className="font-medium text-foreground">{etfName}</span>
              <span className="ml-2">({etfCode})</span>
              <span className="ml-2">当前价格: {currentPrice.toFixed(3)}</span>
            </div>

            {/* Telegram 未配置时的提示 */}
            {error && error.includes("Telegram") ? (
              <div className="mb-4 p-3 bg-amber-500/10 text-amber-600 dark:text-amber-400 rounded-lg text-sm">
                <p>{error}</p>
                <button
                  onClick={() => router.push("/settings/notifications")}
                  className="mt-2 text-primary font-medium underline"
                >
                  去配置
                </button>
              </div>
            ) : (
              <>
                {/* 目标价格 */}
                <div className="mb-4">
                  <label className="block text-sm font-medium mb-1.5">
                    目标价格
                  </label>
                  <input
                    type="number"
                    step="0.001"
                    min="0"
                    value={targetPrice}
                    onChange={(e) => setTargetPrice(e.target.value)}
                    placeholder="输入目标价格"
                    className="w-full px-3 py-2.5 bg-secondary rounded-lg text-foreground outline-none focus:ring-2 focus:ring-primary/50"
                    autoFocus
                  />
                </div>

                {/* 提醒方向 */}
                <div className="mb-4">
                  <label className="block text-sm font-medium mb-1.5">
                    提醒方向
                  </label>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setDirection("below")}
                      className={cn(
                        "flex-1 py-2 rounded-lg text-sm font-medium transition-colors",
                        direction === "below"
                          ? "bg-down/15 text-down border border-down/30"
                          : "bg-secondary text-muted-foreground"
                      )}
                    >
                      ⬇️ 跌破
                    </button>
                    <button
                      onClick={() => setDirection("above")}
                      className={cn(
                        "flex-1 py-2 rounded-lg text-sm font-medium transition-colors",
                        direction === "above"
                          ? "bg-up/15 text-up border border-up/30"
                          : "bg-secondary text-muted-foreground"
                      )}
                    >
                      ⬆️ 突破
                    </button>
                  </div>
                </div>

                {/* 备注 */}
                <div className="mb-4">
                  <label className="block text-sm font-medium mb-1.5">
                    备注（可选）
                  </label>
                  <input
                    type="text"
                    maxLength={200}
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    placeholder="到这个价我要..."
                    className="w-full px-3 py-2.5 bg-secondary rounded-lg text-foreground outline-none focus:ring-2 focus:ring-primary/50"
                  />
                </div>

                {/* 错误/成功提示 */}
                {error && !error.includes("Telegram") && (
                  <div className="mb-4 p-3 bg-destructive/10 text-destructive rounded-lg text-sm">
                    {error}
                  </div>
                )}
                {successMsg && (
                  <div className="mb-4 p-3 bg-green-500/10 text-green-600 dark:text-green-400 rounded-lg text-sm">
                    {successMsg}
                  </div>
                )}

                {/* 按钮 */}
                <div className="flex gap-3">
                  <button
                    onClick={() => setShowDialog(false)}
                    disabled={isSubmitting}
                    className="flex-1 py-2.5 rounded-lg bg-secondary text-muted-foreground font-medium"
                  >
                    取消
                  </button>
                  <button
                    onClick={handleSubmit}
                    disabled={isSubmitting || !targetPrice}
                    className="flex-1 py-2.5 rounded-lg bg-primary text-primary-foreground font-medium disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
                    确认设置
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </>
  )
}
