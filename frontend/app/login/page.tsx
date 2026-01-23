"use client"

import { useState } from "react"
import Link from "next/link"
import { useAuth } from "@/lib/auth-context"
import { useRouter } from "next/navigation"
import { API_BASE_URL } from "@/lib/api"

export default function LoginPage() {
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const { login } = useAuth()
  const router = useRouter()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")

    try {
      const formData = new FormData()
      formData.append("username", username)
      formData.append("password", password)

      const res = await fetch(`${API_BASE_URL}/auth/token`, {
        method: "POST",
        body: formData,
      })

      if (!res.ok) {
        throw new Error("登录失败")
      }

      const data = await res.json()
      await login(data.access_token)
      
      // Check for local watchlist and sync if needed (TODO: Implement sync)
      
      router.push("/settings")
    } catch (err) {
      setError("用户名或密码错误")
    }
  }

  return (
    <div className="container max-w-md mx-auto p-4 pt-10">
      <h1 className="text-2xl font-bold mb-6 text-center">登录 ETFTool</h1>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">用户名</label>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="w-full p-2 border rounded-md bg-background"
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">密码</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full p-2 border rounded-md bg-background"
            required
          />
        </div>
        
        {error && <p className="text-destructive text-sm">{error}</p>}
        
        <button
          type="submit"
          className="w-full py-2 bg-primary text-primary-foreground rounded-md font-medium"
        >
          登录
        </button>
      </form>
      
      <p className="mt-4 text-center text-sm text-muted-foreground">
        没有账号？{" "}
        <Link href="/register" className="text-primary hover:underline">
          去注册
        </Link>
      </p>
    </div>
  )
}
