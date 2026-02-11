import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import React from "react";

// --- Mocks ---
const mockBack = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => ({ code: "510300" }),
  useRouter: () => ({ back: mockBack, push: vi.fn() }),
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: any) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

const mockFetchClient = vi.fn();

vi.mock("@/lib/api", () => ({
  fetchClient: (...args: any[]) => mockFetchClient(...args),
  API_BASE_URL: "http://localhost:8000/api/v1",
}));

vi.mock("@/hooks/use-watchlist", () => ({
  useWatchlist: () => ({
    isWatched: () => false,
    add: vi.fn(),
    remove: vi.fn(),
    isLoaded: true,
  }),
}));

vi.mock("@/hooks/use-settings", () => ({
  useSettings: () => ({ settings: { refreshRate: 0 } }),
}));

// 重型子组件用空占位，避免渲染复杂度
vi.mock("@/components/ETFChart", () => ({
  ETFChart: () => <div data-testid="mock-chart" />,
}));
vi.mock("@/components/TrendAnalysisCard", () => ({
  default: () => <div data-testid="mock-trend" />,
}));
vi.mock("@/components/GridSuggestionCard", () => ({
  default: () => <div data-testid="mock-grid" />,
}));
vi.mock("@/components/FundFlowCard", () => ({
  default: () => <div data-testid="mock-fund-flow" />,
}));
vi.mock("@/components/ValuationCard", () => ({
  default: () => <div data-testid="mock-valuation" />,
}));

import ETFDetailPage from "@/app/etf/[code]/page";

// --- Helpers ---
const baseInfo = {
  code: "510300",
  name: "沪深300ETF",
  price: 3.85,
  change_pct: 1.25,
  volume: 1000000,
  update_time: "2025-01-15 15:00:00",
  market: "已收盘",
};

const baseMetrics = {
  total_return: 0.12,
  cagr: 0.08,
  max_drawdown: -0.15,
  volatility: 0.18,
  risk_level: "中",
  atr: 0.035,
  current_drawdown: -0.03,
  drawdown_days: 60,
};

function setupFetchClient(info: any) {
  mockFetchClient.mockImplementation((url: string) => {
    if (url.includes("/info")) return Promise.resolve(info);
    if (url.includes("/metrics")) return Promise.resolve(baseMetrics);
    if (url.includes("/grid-suggestion")) return Promise.resolve(null);
    if (url.includes("/fund-flow")) return Promise.resolve(null);
    return Promise.resolve(null);
  });
}

beforeEach(() => {
  mockFetchClient.mockReset();
});

describe("ETF 详情页 tags 展示", () => {
  it("有 tags 时渲染全部标签", async () => {
    const info = {
      ...baseInfo,
      tags: [
        { label: "宽基", group: "type" },
        { label: "沪深300", group: "type" },
        { label: "红利", group: "strategy" },
      ],
    };
    setupFetchClient(info);

    render(<ETFDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("宽基")).toBeInTheDocument();
      expect(screen.getByText("沪深300")).toBeInTheDocument();
      expect(screen.getByText("红利")).toBeInTheDocument();
    });
  });

  it("tags 为空时不渲染标签区域", async () => {
    setupFetchClient({ ...baseInfo, tags: [] });

    render(<ETFDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("沪深300ETF")).toBeInTheDocument();
    });

    // 空 tags 不应产生标签 DOM
    expect(screen.queryByText("宽基")).not.toBeInTheDocument();
  });

  it("标签使用正确的配色 class", async () => {
    const info = {
      ...baseInfo,
      tags: [
        { label: "宽基", group: "type" },
        { label: "半导体", group: "industry" },
      ],
    };
    setupFetchClient(info);

    render(<ETFDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("宽基")).toBeInTheDocument();
    });

    const typeTag = screen.getByText("宽基");
    expect(typeTag.className).toContain("bg-blue-500/10");

    const industryTag = screen.getByText("半导体");
    expect(industryTag.className).toContain("bg-purple-500/10");
  });
});
