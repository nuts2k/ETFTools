"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Search, Star, Settings, ArrowLeftRight } from "lucide-react";
import { cn } from "@/lib/utils";

export function BottomNav() {
  const pathname = usePathname();

  const tabs = [
    {
      label: "自选",
      href: "/",
      icon: Star,
    },
    {
      label: "搜索",
      href: "/search",
      icon: Search,
    },
    {
      label: "对比",
      href: "/compare",
      icon: ArrowLeftRight,
    },
    {
      label: "设置",
      href: "/settings",
      icon: Settings,
    },
  ];

  // Hide BottomNav on Detail Page as it has its own floating action button / bottom bar
  const isDetailPage = pathname.startsWith("/etf/");

  if (isDetailPage) return null;

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 bg-background/85 backdrop-blur-md border-t border-border pb-safe">
      <div className="flex h-16 items-center justify-around max-w-md mx-auto">
        {tabs.map((tab) => {
          const isActive = pathname === tab.href;
          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={cn(
                "flex flex-col items-center justify-center gap-1 group w-full h-full transition-colors",
                isActive 
                  ? "text-primary" 
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <div className="relative">
                {isActive && (
                   <div className="absolute -top-1 left-1/2 -translate-x-1/2 w-1 h-1 rounded-full bg-primary mb-1" />
                )}
                <tab.icon 
                  className={cn(
                    "h-6 w-6 transition-transform group-active:scale-95",
                    isActive && "fill-current"
                  )} 
                />
              </div>
              <span className="text-[10px] font-medium tracking-wide">{tab.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
