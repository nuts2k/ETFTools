"use client"

import { useAuth } from "@/lib/auth-context"
import { useRouter } from "next/navigation"
import { useEffect, useState, useCallback } from "react"
import { isAdmin } from "@/lib/admin-guard"
import { ArrowLeft, Shield, UserX, UserCheck } from "lucide-react"
import { fetchAdminUsers, toggleUserAdmin, toggleUserActive, type AdminUser } from "@/lib/api"
import { ActionSheet, type ActionSheetAction } from "@/components/ActionSheet"
import { ConfirmationDialog } from "@/components/ConfirmationDialog"
import { useToast } from "@/components/Toast"
import { cn } from "@/lib/utils"

type FilterKey = "all" | "admin" | "disabled"

const tabs: { key: FilterKey; label: string }[] = [
  { key: "all", label: "全部" },
  { key: "admin", label: "管理员" },
  { key: "disabled", label: "已禁用" },
]

function StatusBadge({ user }: { user: AdminUser }) {
  if (!user.is_active) {
    return (
      <span className="rounded-full px-2 py-0.5 text-xs font-medium bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">
        已禁用
      </span>
    )
  }
  if (user.is_admin) {
    return (
      <span className="rounded-full px-2 py-0.5 text-xs font-medium bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
        管理员
      </span>
    )
  }
  return (
    <span className="rounded-full px-2 py-0.5 text-xs font-medium bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">
      正常
    </span>
  )
}

export default function UsersPage() {
  const { user, token, isLoading } = useAuth()
  const router = useRouter()
  const { toast } = useToast()

  const [users, setUsers] = useState<AdminUser[]>([])
  const [filter, setFilter] = useState<FilterKey>("all")
  const [selectedUser, setSelectedUser] = useState<AdminUser | null>(null)
  const [confirmAction, setConfirmAction] = useState<{ user: AdminUser; action: "admin" | "active" } | null>(null)

  useEffect(() => {
    if (!isLoading && !isAdmin(user)) router.push("/")
  }, [user, isLoading, router])

  const loadUsers = useCallback(async () => {
    if (!token) return
    const params: { is_admin?: boolean; is_active?: boolean } = {}
    if (filter === "admin") params.is_admin = true
    if (filter === "disabled") params.is_active = false
    try {
      const data = await fetchAdminUsers(token, params)
      setUsers(data)
    } catch {
      toast("获取用户列表失败", "error")
    }
  }, [token, filter, toast])

  useEffect(() => { loadUsers() }, [loadUsers])

  const handleUserClick = (targetUser: AdminUser) => {
    if (targetUser.id === user?.id) {
      toast("无法修改自己的权限", "error")
      return
    }
    setSelectedUser(targetUser)
  }

  const handleConfirm = async () => {
    if (!confirmAction || !token) return
    const { user: targetUser, action } = confirmAction
    setConfirmAction(null)

    const prevUsers = [...users]
    setUsers(prev => prev.map(u => {
      if (u.id !== targetUser.id) return u
      return action === "admin"
        ? { ...u, is_admin: !u.is_admin }
        : { ...u, is_active: !u.is_active }
    }))

    try {
      if (action === "admin") {
        await toggleUserAdmin(token, targetUser.id)
        toast(targetUser.is_admin ? `已取消 ${targetUser.username} 的管理员权限` : `已将 ${targetUser.username} 设为管理员`, "success")
      } else {
        await toggleUserActive(token, targetUser.id)
        toast(targetUser.is_active ? `已禁用 ${targetUser.username}` : `已启用 ${targetUser.username}`, "success")
      }
    } catch (e) {
      setUsers(prevUsers)
      toast(e instanceof Error ? e.message : "操作失败", "error")
    }
  }

  if (isLoading || !isAdmin(user)) return null

  const actionSheetActions: ActionSheetAction[] = selectedUser ? [
    {
      label: selectedUser.is_admin ? "取消管理员" : "设为管理员",
      icon: Shield,
      onPress: () => setConfirmAction({ user: selectedUser, action: "admin" }),
    },
    {
      label: selectedUser.is_active ? "禁用账户" : "启用账户",
      icon: selectedUser.is_active ? UserX : UserCheck,
      variant: selectedUser.is_active ? "destructive" : "default",
      onPress: () => setConfirmAction({ user: selectedUser, action: "active" }),
    },
  ] : []

  const confirmTitle = confirmAction?.action === "admin"
    ? (confirmAction.user.is_admin ? "取消管理员权限" : "授予管理员权限")
    : (confirmAction?.user.is_active ? "禁用账户" : "启用账户")

  const confirmVariant = confirmAction?.action === "active" && confirmAction.user.is_active
    ? "destructive" as const
    : "default" as const

  return (
    <div className="flex flex-col min-h-[100dvh] bg-background pb-20">
      <header className="sticky top-0 z-40 bg-background/95 backdrop-blur-md pt-safe border-b border-border/50 transform-gpu backface-hidden">
        <div className="flex h-14 items-center px-5 gap-3">
          <button onClick={() => router.push("/admin")} className="p-1 -ml-1">
            <ArrowLeft className="h-5 w-5 text-foreground" />
          </button>
          <h1 className="text-lg font-semibold text-foreground">用户管理</h1>
        </div>
      </header>

      {/* Filter Tabs */}
      <div className="flex gap-2 px-4 py-3">
        {tabs.map(tab => (
          <button
            key={tab.key}
            onClick={() => setFilter(tab.key)}
            className={cn(
              "px-3 py-1.5 text-sm font-medium rounded-lg transition-colors",
              filter === tab.key
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* User List */}
      <main className="flex-1 w-full max-w-md mx-auto px-4">
        <div className="bg-card rounded-xl overflow-hidden shadow-sm ring-1 ring-border/50 divide-y divide-border/50">
          {users.map(u => (
            <button
              key={u.id}
              onClick={() => handleUserClick(u)}
              className="w-full flex items-center justify-between p-4 hover:bg-secondary/50 transition-colors text-left"
            >
              <div>
                <div className="font-medium">{u.username}</div>
                <div className="text-xs text-muted-foreground mt-0.5">
                  注册于 {new Date(u.created_at).toLocaleDateString("zh-CN")}
                </div>
              </div>
              <StatusBadge user={u} />
            </button>
          ))}
          {users.length === 0 && (
            <div className="p-8 text-center text-sm text-muted-foreground">暂无用户</div>
          )}
        </div>
      </main>

      {/* ActionSheet */}
      <ActionSheet
        isOpen={!!selectedUser}
        title={selectedUser ? `${selectedUser.username} 的操作` : undefined}
        actions={actionSheetActions}
        onClose={() => setSelectedUser(null)}
      />

      {/* Confirmation Dialog */}
      <ConfirmationDialog
        isOpen={!!confirmAction}
        title={confirmTitle}
        description={`确定要对用户 "${confirmAction?.user.username}" 执行此操作吗？`}
        variant={confirmVariant}
        onConfirm={handleConfirm}
        onCancel={() => setConfirmAction(null)}
      />
    </div>
  )
}
