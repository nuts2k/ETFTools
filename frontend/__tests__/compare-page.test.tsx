import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

// --- Mocks ---
const mockReplace = vi.fn();
const mockSearchParams = new URLSearchParams();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace }),
  useSearchParams: () => mockSearchParams,
}));

const mockFetchClient = vi.fn();
vi.mock("@/lib/api", () => ({
  fetchClient: (...args: any[]) => mockFetchClient(...args),
}));

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: any) => <div data-testid="chart-container">{children}</div>,
  LineChart: ({ children }: any) => <div data-testid="line-chart">{children}</div>,
  Line: () => <div data-testid="line" />,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
}));

import ComparePage from "@/app/compare/page";

// --- 测试数据 ---
const mockCompareData = {
  etf_names: { "510300": "沪深300ETF", "510500": "中证500ETF" },
  period_label: "2023-01-01 ~ 2026-01-01",
  warnings: [],
  normalized: {
    dates: ["2023-01-01", "2023-01-02"],
    series: { "510300": [100, 105], "510500": [100, 98] },
  },
  correlation: { "510300_510500": 0.72 },
  metrics: {
    "510300": { cagr: 0.082, total_return: 0.25, actual_years: 3.0, max_drawdown: -0.153, volatility: 0.185, risk_level: "Medium", mdd_date: "2024-01-15", mdd_start: "2023-12-01", mdd_trough: "2024-01-15", mdd_end: "2024-03-01" },
    "510500": { cagr: 0.065, total_return: 0.20, actual_years: 3.0, max_drawdown: -0.18, volatility: 0.21, risk_level: "Medium", mdd_date: "2024-01-15", mdd_start: "2023-12-01", mdd_trough: "2024-01-15", mdd_end: "2024-04-01" },
  },
  temperatures: {
    "510300": { score: 45, level: "cool", factors: { drawdown_score: 40, rsi_score: 50, percentile_score: 45, volatility_score: 42, trend_score: 48 }, rsi_value: 50, percentile_value: 45, percentile_years: 10 },
    "510500": null,
  },
};

const popularTags = [
  { label: "宽基", group: "type" },
  { label: "红利", group: "strategy" },
];

const searchResults = [
  { code: "510300", name: "沪深300ETF", price: 3.9, change_pct: 0.5, volume: 1000 },
  { code: "510500", name: "中证500ETF", price: 5.2, change_pct: -0.3, volume: 2000 },
];

describe("ComparePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // 每次测试前清理 searchParams，避免跨测试污染
    mockSearchParams.delete("codes");
    mockSearchParams.delete("period");
    mockFetchClient.mockImplementation((url: string) => {
      if (url.includes("/tags/popular")) return Promise.resolve(popularTags);
      if (url.includes("/etf/search")) return Promise.resolve(searchResults);
      if (url.includes("/etf/compare")) return Promise.resolve(mockCompareData);
      return Promise.reject(new Error("Unknown URL"));
    });
  });

  it("初始状态显示引导文案", async () => {
    render(<ComparePage />);
    expect(screen.getByText("请添加至少 2 只 ETF 开始对比")).toBeInTheDocument();
  });

  it("点击 + 按钮展开搜索框", async () => {
    render(<ComparePage />);
    const buttons = screen.getAllByRole("button");
    const plusBtn = buttons.find(b => b.querySelector("svg"));
    if (plusBtn) fireEvent.click(plusBtn);
    expect(screen.getByPlaceholderText("搜索 ETF...")).toBeInTheDocument();
  });

  it("搜索展开后显示热门标签", async () => {
    render(<ComparePage />);
    const buttons = screen.getAllByRole("button");
    const plusBtn = buttons.find(b => b.querySelector("svg"));
    if (plusBtn) fireEvent.click(plusBtn);

    await waitFor(() => {
      expect(screen.getByText("宽基")).toBeInTheDocument();
      expect(screen.getByText("红利")).toBeInTheDocument();
    });
  });

  it("warnings 非空时显示淡黄色提示条", async () => {
    const dataWithWarning = {
      ...mockCompareData,
      warnings: ["重叠交易日仅 45 天，对比结果可能不够稳定"],
    };
    mockFetchClient.mockImplementation((url: string) => {
      if (url.includes("/tags/popular")) return Promise.resolve(popularTags);
      if (url.includes("/etf/compare")) return Promise.resolve(dataWithWarning);
      return Promise.resolve([]);
    });

    // 通过 URL 参数初始化已选 ETF 来触发数据加载
    // 清理已在 beforeEach 中统一处理，无需手动 delete
    mockSearchParams.set("codes", "510300,510500");

    render(<ComparePage />);

    await waitFor(() => {
      expect(screen.getByText("重叠交易日仅 45 天，对比结果可能不够稳定")).toBeInTheDocument();
    });
  });
});
