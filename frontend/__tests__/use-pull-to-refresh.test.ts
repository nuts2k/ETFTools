import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { usePullToRefresh } from '@/hooks/use-pull-to-refresh'

function createMockScrollRef(scrollTop = 0) {
  const el = document.createElement('div')
  el.style.overflowY = 'auto'
  Object.defineProperty(el, 'scrollTop', { get: () => scrollTop, configurable: true })
  return { current: el } as React.RefObject<HTMLElement>
}

function fireTouchEvent(el: HTMLElement, type: string, clientX: number, clientY: number) {
  const touch = { clientX, clientY } as Touch
  const event = new TouchEvent(type, {
    touches: type === 'touchend' ? [] : [touch],
    cancelable: true,
  })
  el.dispatchEvent(event)
}

describe('usePullToRefresh', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('should start in idle state with pullDistance 0', () => {
    const scrollRef = createMockScrollRef()
    const { result } = renderHook(() =>
      usePullToRefresh({ onRefresh: vi.fn(), scrollRef })
    )
    expect(result.current.state).toBe('idle')
    expect(result.current.pullDistance).toBe(0)
  })

  it('should not activate when scrollTop > 1', () => {
    const scrollRef = createMockScrollRef(100)
    const { result } = renderHook(() =>
      usePullToRefresh({ onRefresh: vi.fn(), scrollRef })
    )

    act(() => {
      fireTouchEvent(scrollRef.current!, 'touchstart', 100, 100)
      fireTouchEvent(scrollRef.current!, 'touchmove', 100, 200)
    })

    expect(result.current.state).toBe('idle')
    expect(result.current.pullDistance).toBe(0)
  })

  it('should activate when scrollTop is sub-pixel (e.g. 0.5)', () => {
    const scrollRef = createMockScrollRef(0.5)
    const { result } = renderHook(() =>
      usePullToRefresh({ onRefresh: vi.fn(), scrollRef })
    )

    act(() => {
      fireTouchEvent(scrollRef.current!, 'touchstart', 100, 100)
      fireTouchEvent(scrollRef.current!, 'touchmove', 100, 130)
    })

    expect(result.current.state).toBe('pulling')
  })

  it('should late-activate when scrollTop settles to 0 during touchmove', () => {
    let scrollTop = 5
    const el = document.createElement('div')
    el.style.overflowY = 'auto'
    Object.defineProperty(el, 'scrollTop', { get: () => scrollTop, configurable: true })
    const scrollRef = { current: el } as React.RefObject<HTMLElement>

    const { result } = renderHook(() =>
      usePullToRefresh({ onRefresh: vi.fn(), scrollRef })
    )

    // touchstart skipped because scrollTop=5
    act(() => {
      fireTouchEvent(el, 'touchstart', 100, 100)
    })
    expect(result.current.state).toBe('idle')

    // scrollTop settles to 0, touchmove captures start position
    scrollTop = 0
    act(() => {
      fireTouchEvent(el, 'touchmove', 100, 110)
    })
    // First touchmove only records start, doesn't pull yet
    expect(result.current.state).toBe('idle')

    // Next touchmove triggers pulling
    act(() => {
      fireTouchEvent(el, 'touchmove', 100, 140)
    })
    expect(result.current.state).toBe('pulling')
  })

  it('should not activate when disabled', () => {
    const scrollRef = createMockScrollRef(0)
    const { result } = renderHook(() =>
      usePullToRefresh({ onRefresh: vi.fn(), scrollRef, disabled: true })
    )

    act(() => {
      fireTouchEvent(scrollRef.current!, 'touchstart', 100, 100)
      fireTouchEvent(scrollRef.current!, 'touchmove', 100, 200)
    })

    expect(result.current.state).toBe('idle')
  })

  it('should transition to pulling on downward gesture at scrollTop=0', () => {
    const scrollRef = createMockScrollRef(0)
    const { result } = renderHook(() =>
      usePullToRefresh({ onRefresh: vi.fn(), scrollRef })
    )

    act(() => {
      fireTouchEvent(scrollRef.current!, 'touchstart', 100, 100)
      // Move down past direction lock distance (10px)
      fireTouchEvent(scrollRef.current!, 'touchmove', 100, 130)
    })

    expect(result.current.state).toBe('pulling')
    expect(result.current.pullDistance).toBeGreaterThan(0)
  })

  it('should abort on horizontal swipe', () => {
    const scrollRef = createMockScrollRef(0)
    const { result } = renderHook(() =>
      usePullToRefresh({ onRefresh: vi.fn(), scrollRef })
    )

    act(() => {
      fireTouchEvent(scrollRef.current!, 'touchstart', 100, 100)
      // Move horizontally past lock distance
      fireTouchEvent(scrollRef.current!, 'touchmove', 130, 105)
    })

    expect(result.current.state).toBe('idle')
    expect(result.current.pullDistance).toBe(0)
  })

  it('should transition to threshold when pulled past threshold', () => {
    const scrollRef = createMockScrollRef(0)
    const onRefresh = vi.fn().mockResolvedValue(undefined)
    const { result } = renderHook(() =>
      usePullToRefresh({ onRefresh, scrollRef, threshold: 80 })
    )

    act(() => {
      fireTouchEvent(scrollRef.current!, 'touchstart', 100, 0)
      // Pull down far enough to exceed threshold after resistance
      fireTouchEvent(scrollRef.current!, 'touchmove', 100, 120)
    })

    expect(result.current.state).toBe('threshold')
  })

  it('should return to idle when released below threshold', () => {
    const scrollRef = createMockScrollRef(0)
    const { result } = renderHook(() =>
      usePullToRefresh({ onRefresh: vi.fn(), scrollRef, threshold: 80 })
    )

    act(() => {
      fireTouchEvent(scrollRef.current!, 'touchstart', 100, 100)
      fireTouchEvent(scrollRef.current!, 'touchmove', 100, 130)
    })
    expect(result.current.state).toBe('pulling')

    act(() => {
      fireTouchEvent(scrollRef.current!, 'touchend', 100, 130)
    })
    expect(result.current.state).toBe('idle')
    expect(result.current.pullDistance).toBe(0)
  })

  it('should trigger refresh when released at threshold', async () => {
    const scrollRef = createMockScrollRef(0)
    const onRefresh = vi.fn().mockResolvedValue(undefined)
    const { result } = renderHook(() =>
      usePullToRefresh({ onRefresh, scrollRef, threshold: 80 })
    )

    act(() => {
      fireTouchEvent(scrollRef.current!, 'touchstart', 100, 0)
      fireTouchEvent(scrollRef.current!, 'touchmove', 100, 120)
    })
    expect(result.current.state).toBe('threshold')

    await act(async () => {
      fireTouchEvent(scrollRef.current!, 'touchend', 100, 120)
      // Let the refresh promise resolve
      await vi.runAllTimersAsync()
    })

    expect(onRefresh).toHaveBeenCalledOnce()
  })

  it('should enforce cooldown between refreshes', async () => {
    const scrollRef = createMockScrollRef(0)
    const onRefresh = vi.fn().mockResolvedValue(undefined)
    const { result } = renderHook(() =>
      usePullToRefresh({ onRefresh, scrollRef, threshold: 80, cooldown: 3000 })
    )

    // First refresh
    act(() => {
      fireTouchEvent(scrollRef.current!, 'touchstart', 100, 0)
      fireTouchEvent(scrollRef.current!, 'touchmove', 100, 120)
    })
    await act(async () => {
      fireTouchEvent(scrollRef.current!, 'touchend', 100, 120)
      await vi.runAllTimersAsync()
    })
    expect(onRefresh).toHaveBeenCalledOnce()

    // Attempt second refresh immediately (within cooldown)
    act(() => {
      fireTouchEvent(scrollRef.current!, 'touchstart', 100, 0)
      fireTouchEvent(scrollRef.current!, 'touchmove', 100, 120)
    })
    // Should still be idle because cooldown blocks touchstart
    expect(result.current.state).toBe('idle')
  })

  it('should apply resistance curve capping at maxPull', () => {
    const scrollRef = createMockScrollRef(0)
    const { result } = renderHook(() =>
      usePullToRefresh({ onRefresh: vi.fn(), scrollRef, maxPull: 120 })
    )

    act(() => {
      fireTouchEvent(scrollRef.current!, 'touchstart', 100, 0)
      // Pull very far down
      fireTouchEvent(scrollRef.current!, 'touchmove', 100, 500)
    })

    expect(result.current.pullDistance).toBeLessThanOrEqual(120)
  })

  it('should stay in threshold state when pulled very far (no reversal)', () => {
    const scrollRef = createMockScrollRef(0)
    const { result } = renderHook(() =>
      usePullToRefresh({ onRefresh: vi.fn(), scrollRef, threshold: 80, maxPull: 120 })
    )

    act(() => {
      fireTouchEvent(scrollRef.current!, 'touchstart', 100, 0)
      // Pull past threshold
      fireTouchEvent(scrollRef.current!, 'touchmove', 100, 120)
    })
    expect(result.current.state).toBe('threshold')

    // Pull much further — state must NOT revert to 'pulling'
    act(() => {
      fireTouchEvent(scrollRef.current!, 'touchmove', 100, 400)
    })
    expect(result.current.state).toBe('threshold')
    expect(result.current.pullDistance).toBeGreaterThanOrEqual(80)
  })

  it('should use passive touchmove listener (no preventDefault)', () => {
    const scrollRef = createMockScrollRef(0)
    renderHook(() =>
      usePullToRefresh({ onRefresh: vi.fn(), scrollRef })
    )

    const el = scrollRef.current!
    act(() => {
      fireTouchEvent(el, 'touchstart', 100, 100)
    })

    // Fire a downward touchmove past direction lock threshold
    const touch = { clientX: 100, clientY: 115 } as Touch
    const moveEvent = new TouchEvent('touchmove', {
      touches: [touch],
      cancelable: true,
    })
    const spy = vi.spyOn(moveEvent, 'preventDefault')

    act(() => {
      el.dispatchEvent(moveEvent)
    })

    // passive listener cannot call preventDefault
    expect(spy).not.toHaveBeenCalled()
  })

  it('should reach threshold on a single fast large swipe', async () => {
    const scrollRef = createMockScrollRef(0)
    const onRefresh = vi.fn().mockResolvedValue(undefined)
    const { result } = renderHook(() =>
      usePullToRefresh({ onRefresh, scrollRef, threshold: 80, maxPull: 120 })
    )

    // Simulate a fast swipe: one touchstart then one large touchmove
    act(() => {
      fireTouchEvent(scrollRef.current!, 'touchstart', 100, 0)
      fireTouchEvent(scrollRef.current!, 'touchmove', 100, 500)
    })
    expect(result.current.state).toBe('threshold')

    await act(async () => {
      fireTouchEvent(scrollRef.current!, 'touchend', 100, 500)
      await vi.runAllTimersAsync()
    })
    expect(onRefresh).toHaveBeenCalledOnce()
  })
})
