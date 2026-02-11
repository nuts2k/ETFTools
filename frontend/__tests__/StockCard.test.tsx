import { render, screen } from "@testing-library/react"
import { describe, it, expect } from "vitest"
import { StockCard } from "@/components/StockCard"
import type { ETFItem } from "@/lib/api"

const baseETF: ETFItem = {
  code: "510300",
  name: "沪深300ETF",
  price: 3.850,
  change_pct: 1.25,
  volume: 1000000,
}

const etfWithTags: ETFItem = {
  ...baseETF,
  tags: [
    { label: "宽基", group: "type" },
    { label: "沪深300", group: "type" },
    { label: "红利", group: "strategy" },
  ],
}

describe("StockCard tags 展示", () => {
  it("showTags=true 且有 tags 时渲染标签 badge", () => {
    render(<StockCard etf={etfWithTags} showTags={true} />)
    expect(screen.getByText("宽基")).toBeInTheDocument()
    expect(screen.getByText("沪深300")).toBeInTheDocument()
  })

  it("最多展示前 2 个标签", () => {
    render(<StockCard etf={etfWithTags} showTags={true} />)
    expect(screen.getByText("宽基")).toBeInTheDocument()
    expect(screen.getByText("沪深300")).toBeInTheDocument()
    expect(screen.queryByText("红利")).not.toBeInTheDocument()
  })

  it("showTags=false 时不渲染标签", () => {
    render(<StockCard etf={etfWithTags} showTags={false} />)
    expect(screen.queryByText("宽基")).not.toBeInTheDocument()
  })

  it("showTags 默认为 false", () => {
    render(<StockCard etf={etfWithTags} />)
    expect(screen.queryByText("宽基")).not.toBeInTheDocument()
  })

  it("tags 为 undefined 时不报错", () => {
    render(<StockCard etf={baseETF} showTags={true} />)
    expect(screen.getByText("510300")).toBeInTheDocument()
  })

  it("tags 为空数组时不渲染标签区域", () => {
    const etf = { ...baseETF, tags: [] as Array<{ label: string; group: string }> }
    render(<StockCard etf={etf} showTags={true} />)
    expect(screen.getByText("510300")).toBeInTheDocument()
  })
})
