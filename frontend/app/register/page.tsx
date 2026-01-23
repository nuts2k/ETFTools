"use client"

import { useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { API_BASE_URL } from "@/lib/api"

export default function RegisterPage() {
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const router = useRouter()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")

    try {
      const res = await fetch(`${API_BASE_URL}/auth/register`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ username, password }),
      })

      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || "注册失败")
      }

      // Redirect to login on success
      router.push("/login")
    } catch (err: any) {
      setError(err.message)
    }
  }

  return (
    <div className="container max-w-md mx-auto p-4 pt-10">
      <h1 className="text-2xl font-bold mb-6 text-center">注册</h1>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">用户名</label>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="w-full p-2 border rounded-md bg-background"
            required
            minLength={3}
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
            minLength={6}
          />
        </div>
        
        {error && <p className="text-destructive text-sm">{error}</p>}
        
        <button
          type="submit"
          className="w-full py-2 bg-primary text-primary-foreground rounded-md font-medium"
        >
          注册
        </button>
      </form>
      
      <p className="mt-4 text-center text-sm text-muted-foreground">
        已有账号？{" "}
        <Link href="/login" className="text-primary hover:underline">
          去登录
        </Link>
      </p>
    </div>
  )
}
