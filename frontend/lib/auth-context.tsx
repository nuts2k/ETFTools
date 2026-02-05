"use client"

import { createContext, useContext, useEffect, useState, ReactNode } from "react"
import { useRouter } from "next/navigation"
import { API_BASE_URL } from "./api"

interface User {
  id: number
  username: string
  settings: Record<string, any>
  is_admin: boolean
  is_active: boolean
}

interface AuthContextType {
  user: User | null
  token: string | null
  isLoading: boolean
  login: (token: string) => Promise<void>
  logout: () => void
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const router = useRouter()

  useEffect(() => {
    // Load token from localStorage on mount
    const storedToken = localStorage.getItem("access_token")
    if (storedToken) {
      setToken(storedToken)
      fetchUser(storedToken)
    } else {
      setIsLoading(false)
    }
  }, [])

  const fetchUser = async (authToken: string) => {
    try {
      const res = await fetch(`${API_BASE_URL}/users/me`, {
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
      })
      if (res.ok) {
        const userData = await res.json()
        setUser(userData)
      } else {
        // Token invalid
        logout()
      }
    } catch (error) {
      console.error("Failed to fetch user", error)
    } finally {
      setIsLoading(false)
    }
  }

  const login = async (newToken: string) => {
    localStorage.setItem("access_token", newToken)
    setToken(newToken)
    await fetchUser(newToken)
  }

  const logout = () => {
    localStorage.removeItem("access_token")
    setToken(null)
    setUser(null)
    router.push("/login")
  }

  const refreshUser = async () => {
    if (token) {
      await fetchUser(token)
    }
  }

  return (
    <AuthContext.Provider value={{ user, token, isLoading, login, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}
