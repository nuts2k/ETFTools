import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { BottomNav } from "@/components/BottomNav";
import { ThemeProvider } from "@/components/theme-provider";
import { AuthProvider } from "@/lib/auth-context";

const inter = Inter({ subsets: ["latin"] });

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f6f7f8" },
    { media: "(prefers-color-scheme: dark)", color: "#0f172a" },
  ],
};

export const metadata: Metadata = {
  title: "ETFTool (A股版)",
  description: "专业的 A 股 ETF 前复权收益分析工具",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "ETFTool",
  },
  manifest: "/manifest.json",
  icons: {
    apple: "/apple-touch-icon.png",
  },
};

import { WatchlistProvider } from "@/lib/watchlist-context";
import { SettingsProvider } from "@/lib/settings-context";
import { ToastProvider } from "@/components/Toast";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body className={`${inter.className} bg-background text-foreground antialiased`}>
        <AuthProvider>
          <SettingsProvider>
            <WatchlistProvider>
              <ThemeProvider
                attribute="class"
                defaultTheme="system"
                enableSystem
                disableTransitionOnChange
              >
                <ToastProvider>
                  <main className="min-h-[100dvh] pb-20">
                    {children}
                  </main>
                  <BottomNav />
                </ToastProvider>
              </ThemeProvider>
            </WatchlistProvider>
          </SettingsProvider>
        </AuthProvider>
      </body>
    </html>
  );
}

