"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Search, Star, Settings } from "lucide-react";
import { cn } from "@/lib/utils";

export function BottomNav() {
  const pathname = usePathname();

  const tabs = [
    {
      label: "搜索",
      href: "/",
      icon: Search,
    },
    {
      label: "自选",
      href: "/watchlist",
      icon: Star,
    },
    {
      label: "设置",
      href: "/settings",
      icon: Settings,
    },
  ];

  // 如果在详情页 (e.g. /etf/510300)，通常不显示底部导航，或者保持显示？
  // 移动端习惯通常是详情页会覆盖导航，但 Web App 有时保留。
  // 根据 PRD "底部操作栏" 在详情页是 "加入/移除自选"，这意味着详情页有自己的底部栏。
  // 因此，我们在详情页隐藏全局 BottomNav。
  const isDetailPage = pathname.startsWith("/etf/");

  if (isDetailPage) return null;

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 border-t bg-background pb-safe">
      <div className="flex h-16 items-center justify-around">
        {tabs.map((tab) => {
          const isActive = pathname === tab.href;
          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={cn(
                "flex flex-col items-center justify-center space-y-1 w-full h-full",
                isActive ? "text-primary" : "text-muted-foreground hover:text-foreground"
              )}
            >
              <tab.icon className="h-6 w-6" />
              <span className="text-[10px] font-medium">{tab.label}</span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
