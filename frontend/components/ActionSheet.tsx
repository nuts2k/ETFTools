"use client"

import { cn } from "@/lib/utils"
import { useEffect, useState } from "react"
import { createPortal } from "react-dom"
import { type LucideIcon } from "lucide-react"

export interface ActionSheetAction {
  label: string
  icon?: LucideIcon
  variant?: "default" | "destructive"
  onPress: () => void
}

interface ActionSheetProps {
  isOpen: boolean
  title?: string
  actions: ActionSheetAction[]
  onClose: () => void
}

export function ActionSheet({ isOpen, title, actions, onClose }: ActionSheetProps) {
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
    if (isOpen) {
      document.body.style.overflow = "hidden"
    } else {
      document.body.style.overflow = "unset"
    }
    return () => {
      document.body.style.overflow = "unset"
    }
  }, [isOpen])

  if (!mounted || !isOpen) return null

  const handleAction = (action: ActionSheetAction) => {
    action.onPress()
    onClose()
  }

  const content = (
    <div className="fixed inset-0 z-[60]">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm animate-in fade-in duration-200"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="absolute bottom-0 left-0 right-0 pb-safe animate-in slide-in-from-bottom duration-200">
        {/* Action list */}
        <div className="mx-3 bg-card rounded-2xl overflow-hidden ring-1 ring-border/50">
          {title && (
            <div className="px-4 py-3 text-center text-sm text-muted-foreground border-b border-border/50">
              {title}
            </div>
          )}
          {actions.map((action, index) => {
            const Icon = action.icon
            return (
              <button
                key={index}
                className={cn(
                  "w-full p-4 min-h-[56px] flex items-center justify-center gap-3 text-base font-medium transition-colors active:bg-secondary/80",
                  index > 0 && "border-t border-border/50",
                  action.variant === "destructive" ? "text-destructive" : "text-foreground"
                )}
                onClick={() => handleAction(action)}
              >
                {Icon && <Icon className="h-5 w-5" />}
                {action.label}
              </button>
            )
          })}
        </div>

        {/* Cancel button */}
        <div className="mx-3 mt-2 mb-3">
          <button
            className="w-full bg-card rounded-2xl p-4 text-base font-semibold text-primary ring-1 ring-border/50 transition-colors active:bg-secondary/80"
            onClick={onClose}
          >
            取消
          </button>
        </div>
      </div>
    </div>
  )

  return createPortal(content, document.body)
}
