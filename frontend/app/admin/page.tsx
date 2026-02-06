"use client"

import { useAuth } from "@/lib/auth-context"
import { useRouter } from "next/navigation"
import { useEffect, useState } from "react"
import { isAdmin } from "@/lib/admin-guard"
import { Users, Settings, ArrowLeft, ChevronRight } from "lucide-react"
import { fetchAdminUsers, fetchSystemConfig, type AdminUser, type SystemConfig } from "@/lib/api"
import { useToast } from "@/components/Toast"
import Link from "next/link"

export default function AdminPage() {
  const { user, token, isLoading } = useAuth()
  const router = useRouter()
  const { toast } = useToast()
  const [users, setUsers] = useState<AdminUser[]>([])
  const [config, setConfig] = useState<SystemConfig | null>(null)

  useEffect(() => {
    if (!isLoading && !isAdmin(user)) {
      router.push("/")
    }
  }, [user, isLoading, router])

  useEffect(() => {
    if (!token || !isAdmin(user)) return
    Promise.all([
      fetchAdminUsers(token),
      fetchSystemConfig(token),
    ]).then(([usersData, configData]) => {
      setUsers(usersData)
      setConfig(configData)
    }).catch(() => {
      toast("加载管理数据失败", "error")
    })
  }, [token, user, toast])

  if (isLoading || !isAdmin(user)) {
    return null
  }

  const adminCount = users.filter(u => u.is_admin).length

  return (
    <div className="flex flex-col min-h-[100dvh] bg-background pb-20">
      <header className="sticky top-0 z-40 bg-background/95 backdrop-blur-md pt-safe border-b border-border/50 transform-gpu backface-hidden">
        <div className="flex h-14 items-center px-5 gap-3">
          <button onClick={() => router.push("/settings")} className="p-1 -ml-1">
            <ArrowLeft className="h-5 w-5 text-foreground" />
          </button>
          <h1 className="text-lg font-semibold text-foreground">管理员控制台</h1>
        </div>
      </header>

      <main className="flex-1 w-full max-w-md mx-auto px-4 pt-6 space-y-6">
        {/* Stats Grid */}
        <section>
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-card rounded-xl p-4 ring-1 ring-border/50">
              <div className="text-xs text-muted-foreground">用户总数</div>
              <div className="text-2xl font-bold mt-1">{users.length}</div>
            </div>
            <div className="bg-card rounded-xl p-4 ring-1 ring-border/50">
              <div className="text-xs text-muted-foreground">管理员数</div>
              <div className="text-2xl font-bold mt-1">{adminCount}</div>
            </div>
            <div className="bg-card rounded-xl p-4 ring-1 ring-border/50">
              <div className="text-xs text-muted-foreground">注册状态</div>
              <div className={`text-2xl font-bold mt-1 ${config?.registration_enabled ? "text-green-500" : "text-red-500"}`}>
                {config ? (config.registration_enabled ? "开放" : "关闭") : "—"}
              </div>
            </div>
            <div className="bg-card rounded-xl p-4 ring-1 ring-border/50">
              <div className="text-xs text-muted-foreground">自选上限</div>
              <div className="text-2xl font-bold mt-1">{config?.max_watchlist_items ?? "—"}</div>
            </div>
          </div>
        </section>

        {/* Navigation */}
        <section>
          <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2 pl-3">功能</h2>
          <div className="bg-card rounded-xl overflow-hidden shadow-sm ring-1 ring-border/50 divide-y divide-border/50">
            <Link href="/admin/users" className="flex items-center gap-3 p-4 hover:bg-secondary/50 transition-colors">
              <Users className="h-5 w-5 text-primary" />
              <span className="font-medium flex-1">用户管理</span>
              <ChevronRight className="h-5 w-5 text-muted-foreground/50" />
            </Link>
            <Link href="/admin/system" className="flex items-center gap-3 p-4 hover:bg-secondary/50 transition-colors">
              <Settings className="h-5 w-5 text-primary" />
              <span className="font-medium flex-1">系统设置</span>
              <ChevronRight className="h-5 w-5 text-muted-foreground/50" />
            </Link>
          </div>
        </section>
      </main>
    </div>
  )
}
