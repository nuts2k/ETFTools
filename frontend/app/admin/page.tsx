"use client"

import { useAuth } from "@/lib/auth-context"
import { useRouter } from "next/navigation"
import { useEffect } from "react"
import { isAdmin } from "@/lib/admin-guard"
import { Users, Settings, Shield } from "lucide-react"

export default function AdminPage() {
  const { user, isLoading } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!isLoading && !isAdmin(user)) {
      router.push("/")
    }
  }, [user, isLoading, router])

  if (isLoading || !isAdmin(user)) {
    return null
  }

  return (
    <div className="container mx-auto p-4 pb-20">
      <h1 className="text-2xl font-bold mb-6 flex items-center gap-2">
        <Shield className="h-6 w-6" />
        管理员控制台
      </h1>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-card rounded-xl p-4 shadow-sm ring-1 ring-border/50">
          <div className="flex items-center gap-2 font-semibold mb-2">
            <Users className="h-5 w-5" />
            用户管理
          </div>
          <p className="text-sm text-muted-foreground">管理用户账户和权限</p>
        </div>
        <div className="bg-card rounded-xl p-4 shadow-sm ring-1 ring-border/50">
          <div className="flex items-center gap-2 font-semibold mb-2">
            <Settings className="h-5 w-5" />
            系统设置
          </div>
          <p className="text-sm text-muted-foreground">配置系统全局设置</p>
        </div>
      </div>
    </div>
  )
}
