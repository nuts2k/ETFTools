"use client"

import { createContext, useContext, useState, useCallback, useEffect } from "react"
import { createPortal } from "react-dom"
import { CheckCircle, XCircle } from "lucide-react"
import { cn } from "@/lib/utils"

type ToastVariant = "success" | "error"

interface ToastContextType {
  toast: (message: string, variant?: ToastVariant) => void
}

interface ToastState {
  message: string
  variant: ToastVariant
  key: number
}

const ToastContext = createContext<ToastContextType | null>(null)

export function useToast(): ToastContextType {
  const context = useContext(ToastContext)
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider")
  }
  return context
}

function ToastContainer({ state }: { state: ToastState | null }) {
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  if (!mounted || !state) return null

  const Icon = state.variant === "success" ? CheckCircle : XCircle
  const iconColor = state.variant === "success" ? "text-green-500" : "text-red-500"

  const content = (
    <div className="fixed top-0 left-0 right-0 z-[70] pt-safe pointer-events-none">
      <div className="px-4 pt-4 flex justify-center" key={state.key}>
        <div className={cn(
          "bg-card rounded-xl shadow-lg ring-1 ring-border/50 px-4 py-3 max-w-sm w-full",
          "flex items-center gap-3 pointer-events-auto",
          "animate-in fade-in slide-in-from-top-2 duration-300"
        )}>
          <Icon className={cn("h-5 w-5 flex-shrink-0", iconColor)} />
          <span className="text-sm font-medium text-foreground">{state.message}</span>
        </div>
      </div>
    </div>
  )

  return createPortal(content, document.body)
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<ToastState | null>(null)

  const toast = useCallback((message: string, variant: ToastVariant = "success") => {
    setState({ message, variant, key: Date.now() })
  }, [])

  useEffect(() => {
    if (!state) return
    const timer = setTimeout(() => setState(null), 2500)
    return () => clearTimeout(timer)
  }, [state])

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <ToastContainer state={state} />
    </ToastContext.Provider>
  )
}
