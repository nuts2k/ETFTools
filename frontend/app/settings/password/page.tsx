"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { ChevronLeft } from "lucide-react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { API_BASE_URL } from "@/lib/api";

export default function ChangePasswordPage() {
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const router = useRouter();
  const { user, token, isLoading } = useAuth();

  useEffect(() => {
    if (!isLoading && !user) {
      router.push("/login");
    }
  }, [user, isLoading, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");

    if (newPassword !== confirmPassword) {
      setError("新密码两次输入不一致");
      return;
    }

    if (newPassword.length < 6) {
        setError("新密码长度不能少于6位");
        return;
    }

    setIsSubmitting(true);

    try {
      const res = await fetch(`${API_BASE_URL}/auth/password`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({
          old_password: oldPassword,
          new_password: newPassword
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "修改密码失败");
      }

      setSuccess("密码修改成功");
      setOldPassword("");
      setNewPassword("");
      setConfirmPassword("");
      
      // Optional: Redirect back after delay
      setTimeout(() => {
        router.back();
      }, 1500);
      
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading || !user) {
    return null;
  }

  return (
    <div className="flex flex-col min-h-[100dvh] bg-background pb-20">
      <header className="sticky top-0 z-40 bg-background/95 backdrop-blur-md pt-safe border-b border-border/50 transform-gpu backface-hidden">
        <div className="flex h-14 items-center px-2">
          <Link href="/settings" className="p-2 hover:bg-secondary/50 rounded-full transition-colors">
            <ChevronLeft className="h-6 w-6 text-foreground" />
          </Link>
          <h1 className="text-lg font-bold tracking-tight text-foreground ml-2">修改密码</h1>
        </div>
      </header>

      <main className="flex-1 w-full max-w-md mx-auto px-4 pt-6">
        <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-4">
                <div>
                    <label className="block text-sm font-medium mb-1.5 pl-1">当前密码</label>
                    <input
                        type="password"
                        value={oldPassword}
                        onChange={(e) => setOldPassword(e.target.value)}
                        className="w-full h-12 px-4 rounded-xl border border-border bg-card focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all"
                        placeholder="请输入当前密码"
                        required
                    />
                </div>
                <div>
                    <label className="block text-sm font-medium mb-1.5 pl-1">新密码</label>
                    <input
                        type="password"
                        value={newPassword}
                        onChange={(e) => setNewPassword(e.target.value)}
                        className="w-full h-12 px-4 rounded-xl border border-border bg-card focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all"
                        placeholder="请输入新密码（至少6位）"
                        required
                        minLength={6}
                    />
                </div>
                <div>
                    <label className="block text-sm font-medium mb-1.5 pl-1">确认新密码</label>
                    <input
                        type="password"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        className="w-full h-12 px-4 rounded-xl border border-border bg-card focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all"
                        placeholder="请再次输入新密码"
                        required
                        minLength={6}
                    />
                </div>
            </div>

            {error && (
                <div className="p-3 rounded-lg bg-destructive/10 text-destructive text-sm font-medium">
                    {error}
                </div>
            )}
            
            {success && (
                <div className="p-3 rounded-lg bg-green-500/10 text-green-600 dark:text-green-400 text-sm font-medium">
                    {success}
                </div>
            )}

            <button
                type="submit"
                disabled={isSubmitting}
                className="w-full py-3.5 bg-primary text-primary-foreground rounded-xl font-semibold shadow-sm hover:bg-primary/90 disabled:opacity-70 disabled:cursor-not-allowed transition-all active:scale-[0.98]"
            >
                {isSubmitting ? "提交中..." : "修改密码"}
            </button>
        </form>
      </main>
    </div>
  );
}
