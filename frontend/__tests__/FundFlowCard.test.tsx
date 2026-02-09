import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import FundFlowCard from "@/components/FundFlowCard";
import type { FundFlowData } from "@/lib/api";

describe("FundFlowCard", () => {
  const mockData: FundFlowData = {
    code: "510300",
    name: "沪深300ETF",
    current_scale: {
      shares: 910.62,
      scale: 3578.54,
      update_date: "2025-01-15",
      exchange: "SSE",
    },
    rank: {
      rank: 3,
      total_count: 593,
      percentile: 99.5,
      category: "股票型ETF",
    },
    historical_available: true,
    data_points: 100,
  };

  it("renders skeleton when loading", () => {
    render(<FundFlowCard data={null} isLoading={true} />);

    // Check for skeleton elements with animate-pulse class
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("returns null when no data and not loading", () => {
    const { container } = render(<FundFlowCard data={null} isLoading={false} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders shares and scale correctly", () => {
    render(<FundFlowCard data={mockData} isLoading={false} />);

    // Check for shares
    expect(screen.getByText(/910\.62 亿份/)).toBeInTheDocument();

    // Check for scale
    expect(screen.getByText(/3,578\.54 亿元/)).toBeInTheDocument();
  });

  it("renders rank info", () => {
    render(<FundFlowCard data={mockData} isLoading={false} />);

    // Check for rank
    expect(screen.getByText(/第 3 名 \/ 593 只/)).toBeInTheDocument();

    // Check for percentile
    expect(screen.getByText(/超过 99\.5% 的股票型ETF/)).toBeInTheDocument();
  });

  it("renders without rank when rank is null", () => {
    const dataWithoutRank: FundFlowData = {
      ...mockData,
      rank: null,
    };

    render(<FundFlowCard data={dataWithoutRank} isLoading={false} />);

    // Should still render shares
    expect(screen.getByText(/910\.62 亿份/)).toBeInTheDocument();

    // Should not render rank section
    expect(screen.queryByText(/规模排名/)).not.toBeInTheDocument();
  });

  it("renders without scale when scale is null", () => {
    const dataWithoutScale: FundFlowData = {
      ...mockData,
      current_scale: {
        ...mockData.current_scale,
        scale: null,
      },
    };

    render(<FundFlowCard data={dataWithoutScale} isLoading={false} />);

    // Should still render shares
    expect(screen.getByText(/910\.62 亿份/)).toBeInTheDocument();

    // Should show "暂无规模数据"
    expect(screen.getByText(/暂无规模数据/)).toBeInTheDocument();
  });

  it("renders update date in footer", () => {
    render(<FundFlowCard data={mockData} isLoading={false} />);

    // Check for update date
    expect(screen.getByText(/数据日期: 2025-01-15/)).toBeInTheDocument();
  });
});
