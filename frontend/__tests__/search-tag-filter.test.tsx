import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import React from "react";

// --- Mocks ---
vi.mock("next/navigation", () => ({
  useRouter: () => ({ back: vi.fn(), push: vi.fn() }),
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

import SearchPage from "@/app/search/page";

const popularTags = [
  { label: "宽基", group: "type" },
  { label: "半导体", group: "industry" },
  { label: "红利", group: "strategy" },
];

const searchResults = [
  { code: "510300", name: "沪深300ETF", price: 3.85, change_pct: 1.0, tags: [{ label: "宽基", group: "type" }] },
];

beforeEach(() => {
  mockFetchClient.mockReset();
  mockFetchClient.mockImplementation((url: string) => {
    if (url.includes("/tags/popular")) return Promise.resolve(popularTags);
    if (url.includes("tag=")) return Promise.resolve(searchResults);
    return Promise.resolve([]);
  });
});

describe("搜索页标签筛选", () => {
  it("加载后渲染热门标签行", async () => {
    render(<SearchPage />);

    await waitFor(() => {
      expect(screen.getByText("宽基")).toBeInTheDocument();
      expect(screen.getByText("半导体")).toBeInTheDocument();
      expect(screen.getByText("红利")).toBeInTheDocument();
    });
  });

  it("标签行具有正确的无障碍属性", async () => {
    render(<SearchPage />);

    await waitFor(() => {
      expect(screen.getByRole("radiogroup")).toHaveAttribute("aria-label", "按标签筛选 ETF");
    });

    const radios = screen.getAllByRole("radio");
    expect(radios.length).toBe(3);
    radios.forEach((radio) => {
      expect(radio).toHaveAttribute("aria-checked", "false");
    });
  });

  it("点击标签后 aria-checked 变为 true", async () => {
    render(<SearchPage />);

    await waitFor(() => {
      expect(screen.getByText("宽基")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("宽基"));

    await waitFor(() => {
      expect(screen.getByText("宽基").closest("button")).toHaveAttribute("aria-checked", "true");
    });
  });

  it("再次点击同一标签取消选中", async () => {
    render(<SearchPage />);

    await waitFor(() => {
      expect(screen.getByText("宽基")).toBeInTheDocument();
    });

    const btn = screen.getByText("宽基");
    fireEvent.click(btn);

    await waitFor(() => {
      expect(btn.closest("button")).toHaveAttribute("aria-checked", "true");
    });

    fireEvent.click(btn);

    await waitFor(() => {
      expect(btn.closest("button")).toHaveAttribute("aria-checked", "false");
    });
  });

  it("点击标签显示筛选结果标题", async () => {
    render(<SearchPage />);

    await waitFor(() => {
      expect(screen.getByText("宽基")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("宽基"));

    await waitFor(() => {
      expect(screen.getByText("「宽基」相关")).toBeInTheDocument();
    });
  });

  it("输入文字后标签行隐藏", async () => {
    render(<SearchPage />);

    await waitFor(() => {
      expect(screen.getByText("宽基")).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText("输入代码或名称 (如 沪深300)");
    fireEvent.change(input, { target: { value: "300" } });

    await waitFor(() => {
      const radiogroup = screen.getByRole("radiogroup");
      expect(radiogroup.parentElement).toHaveClass("hidden");
    });
  });
});
