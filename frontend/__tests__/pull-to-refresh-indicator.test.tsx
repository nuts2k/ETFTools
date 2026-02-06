import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { PullToRefreshIndicator } from '@/components/PullToRefreshIndicator'

describe('PullToRefreshIndicator', () => {
  it('should be hidden in idle state', () => {
    const { container } = render(
      <PullToRefreshIndicator pullDistance={0} state="idle" threshold={80} />
    )
    const outer = container.firstElementChild as HTMLElement
    expect(outer.style.height).toBe('0px')
    expect(outer.style.opacity).toBe('0')
  })

  it('should show "下拉刷新" in pulling state', () => {
    render(
      <PullToRefreshIndicator pullDistance={40} state="pulling" threshold={80} />
    )
    expect(screen.getByText('下拉刷新')).toBeInTheDocument()
  })

  it('should show "释放刷新" in threshold state', () => {
    render(
      <PullToRefreshIndicator pullDistance={90} state="threshold" threshold={80} />
    )
    expect(screen.getByText('释放刷新')).toBeInTheDocument()
  })

  it('should show "正在刷新..." in refreshing state', () => {
    const { container } = render(
      <PullToRefreshIndicator pullDistance={0} state="refreshing" threshold={80} />
    )
    expect(screen.getByText('正在刷新...')).toBeInTheDocument()
    // Should use fixed height 48px, not pullDistance
    const outer = container.firstElementChild as HTMLElement
    expect(outer.style.height).toBe('48px')
  })

  it('should show "刷新完成" in complete state with fixed height', () => {
    const { container } = render(
      <PullToRefreshIndicator pullDistance={0} state="complete" threshold={80} />
    )
    expect(screen.getByText('刷新完成')).toBeInTheDocument()
    const outer = container.firstElementChild as HTMLElement
    expect(outer.style.height).toBe('48px')
  })
})
