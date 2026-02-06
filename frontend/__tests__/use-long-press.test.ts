import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useLongPress } from '@/hooks/use-long-press'

function fireTouchEvent(
  handlers: ReturnType<typeof useLongPress>,
  type: 'touchstart' | 'touchmove' | 'touchend',
  clientX: number,
  clientY: number
) {
  const touch = { clientX, clientY } as Touch
  const event = {
    touches: type === 'touchend' ? [] : [touch],
    target: document.createElement('div'),
    preventDefault: vi.fn(),
  } as unknown as React.TouchEvent

  if (type === 'touchstart') {
    handlers.onTouchStart(event)
  } else if (type === 'touchmove') {
    handlers.onTouchMove(event)
  } else {
    handlers.onTouchEnd(event)
  }
}

function fireMouseEvent(
  handlers: ReturnType<typeof useLongPress>,
  type: 'mousedown' | 'mousemove' | 'mouseup' | 'mouseleave',
  clientX: number,
  clientY: number
) {
  const event = {
    button: 0,
    clientX,
    clientY,
    target: document.createElement('div'),
    preventDefault: vi.fn(),
  } as unknown as React.MouseEvent

  if (type === 'mousedown') {
    handlers.onMouseDown(event)
  } else if (type === 'mousemove') {
    handlers.onMouseMove(event)
  } else if (type === 'mouseup') {
    handlers.onMouseUp(event)
  } else {
    handlers.onMouseLeave(event)
  }
}

describe('useLongPress', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('Quick tap behavior', () => {
    it('should trigger onClick on quick tap without movement (touch)', () => {
      const onLongPress = vi.fn()
      const onClick = vi.fn()
      const { result } = renderHook(() =>
        useLongPress(onLongPress, onClick, { delay: 500 })
      )

      act(() => {
        fireTouchEvent(result.current, 'touchstart', 100, 100)
        fireTouchEvent(result.current, 'touchend', 100, 100)
      })

      expect(onClick).toHaveBeenCalledOnce()
      expect(onLongPress).not.toHaveBeenCalled()
    })

    it('should trigger onClick on quick tap without movement (mouse)', () => {
      const onLongPress = vi.fn()
      const onClick = vi.fn()
      const { result } = renderHook(() =>
        useLongPress(onLongPress, onClick, { delay: 500 })
      )

      act(() => {
        fireMouseEvent(result.current, 'mousedown', 100, 100)
        fireMouseEvent(result.current, 'mouseup', 100, 100)
      })

      expect(onClick).toHaveBeenCalledOnce()
      expect(onLongPress).not.toHaveBeenCalled()
    })

    it('should trigger onClick with small movement (<10px)', () => {
      const onLongPress = vi.fn()
      const onClick = vi.fn()
      const { result } = renderHook(() =>
        useLongPress(onLongPress, onClick, { delay: 500 })
      )

      act(() => {
        fireTouchEvent(result.current, 'touchstart', 100, 100)
        fireTouchEvent(result.current, 'touchmove', 105, 105) // 7px diagonal
        fireTouchEvent(result.current, 'touchend', 105, 105)
      })

      expect(onClick).toHaveBeenCalledOnce()
      expect(onLongPress).not.toHaveBeenCalled()
    })
  })

  describe('Scroll blocking behavior', () => {
    it('should block onClick when scrolling >10px vertically', () => {
      const onLongPress = vi.fn()
      const onClick = vi.fn()
      const { result } = renderHook(() =>
        useLongPress(onLongPress, onClick, { delay: 500 })
      )

      act(() => {
        fireTouchEvent(result.current, 'touchstart', 100, 100)
        fireTouchEvent(result.current, 'touchmove', 100, 120) // 20px down
        fireTouchEvent(result.current, 'touchend', 100, 120)
      })

      expect(onClick).not.toHaveBeenCalled()
      expect(onLongPress).not.toHaveBeenCalled()
    })

    it('should block onClick when scrolling >10px horizontally', () => {
      const onLongPress = vi.fn()
      const onClick = vi.fn()
      const { result } = renderHook(() =>
        useLongPress(onLongPress, onClick, { delay: 500 })
      )

      act(() => {
        fireTouchEvent(result.current, 'touchstart', 100, 100)
        fireTouchEvent(result.current, 'touchmove', 120, 100) // 20px right
        fireTouchEvent(result.current, 'touchend', 120, 100)
      })

      expect(onClick).not.toHaveBeenCalled()
      expect(onLongPress).not.toHaveBeenCalled()
    })

    it('should block onClick when scrolling exactly 11px (boundary test)', () => {
      const onLongPress = vi.fn()
      const onClick = vi.fn()
      const { result } = renderHook(() =>
        useLongPress(onLongPress, onClick, { delay: 500 })
      )

      act(() => {
        fireTouchEvent(result.current, 'touchstart', 100, 100)
        fireTouchEvent(result.current, 'touchmove', 100, 111) // exactly 11px
        fireTouchEvent(result.current, 'touchend', 100, 111)
      })

      expect(onClick).not.toHaveBeenCalled()
      expect(onLongPress).not.toHaveBeenCalled()
    })
  })

  describe('Long press behavior', () => {
    it('should trigger onLongPress after delay without movement', () => {
      const onLongPress = vi.fn()
      const onClick = vi.fn()
      const { result } = renderHook(() =>
        useLongPress(onLongPress, onClick, { delay: 500 })
      )

      act(() => {
        fireTouchEvent(result.current, 'touchstart', 100, 100)
        vi.advanceTimersByTime(500)
      })

      expect(onLongPress).toHaveBeenCalledOnce()
      expect(onClick).not.toHaveBeenCalled()
    })

    it('should block onClick after long press triggers', () => {
      const onLongPress = vi.fn()
      const onClick = vi.fn()
      const { result } = renderHook(() =>
        useLongPress(onLongPress, onClick, { delay: 500 })
      )

      act(() => {
        fireTouchEvent(result.current, 'touchstart', 100, 100)
        vi.advanceTimersByTime(500)
      })

      expect(onLongPress).toHaveBeenCalledOnce()

      act(() => {
        fireTouchEvent(result.current, 'touchend', 100, 100)
      })

      expect(onClick).not.toHaveBeenCalled()
    })

    it('should cancel long press when moving >10px', () => {
      const onLongPress = vi.fn()
      const onClick = vi.fn()
      const { result } = renderHook(() =>
        useLongPress(onLongPress, onClick, { delay: 500 })
      )

      act(() => {
        fireTouchEvent(result.current, 'touchstart', 100, 100)
        vi.advanceTimersByTime(200) // Partial delay
        fireTouchEvent(result.current, 'touchmove', 100, 120) // Move >10px
        vi.advanceTimersByTime(300) // Complete remaining time
      })

      expect(onLongPress).not.toHaveBeenCalled()
    })

    it('should block onClick when moving during long press', () => {
      const onLongPress = vi.fn()
      const onClick = vi.fn()
      const { result } = renderHook(() =>
        useLongPress(onLongPress, onClick, { delay: 500 })
      )

      act(() => {
        fireTouchEvent(result.current, 'touchstart', 100, 100)
        vi.advanceTimersByTime(200)
        fireTouchEvent(result.current, 'touchmove', 100, 120) // Move >10px
        fireTouchEvent(result.current, 'touchend', 100, 120)
      })

      expect(onLongPress).not.toHaveBeenCalled()
      expect(onClick).not.toHaveBeenCalled()
    })

    it('should use custom delay when provided', () => {
      const onLongPress = vi.fn()
      const onClick = vi.fn()
      const { result } = renderHook(() =>
        useLongPress(onLongPress, onClick, { delay: 1000 })
      )

      act(() => {
        fireTouchEvent(result.current, 'touchstart', 100, 100)
        vi.advanceTimersByTime(500)
      })

      expect(onLongPress).not.toHaveBeenCalled()

      act(() => {
        vi.advanceTimersByTime(500)
      })

      expect(onLongPress).toHaveBeenCalledOnce()
    })
  })

  describe('Mouse leave behavior', () => {
    it('should block onClick on mouse leave', () => {
      const onLongPress = vi.fn()
      const onClick = vi.fn()
      const { result } = renderHook(() =>
        useLongPress(onLongPress, onClick, { delay: 500 })
      )

      act(() => {
        fireMouseEvent(result.current, 'mousedown', 100, 100)
        fireMouseEvent(result.current, 'mouseleave', 100, 100)
      })

      expect(onClick).not.toHaveBeenCalled()
      expect(onLongPress).not.toHaveBeenCalled()
    })

    it('should cancel long press timer on mouse leave', () => {
      const onLongPress = vi.fn()
      const onClick = vi.fn()
      const { result } = renderHook(() =>
        useLongPress(onLongPress, onClick, { delay: 500 })
      )

      act(() => {
        fireMouseEvent(result.current, 'mousedown', 100, 100)
        vi.advanceTimersByTime(200)
        fireMouseEvent(result.current, 'mouseleave', 100, 100)
        vi.advanceTimersByTime(300)
      })

      expect(onLongPress).not.toHaveBeenCalled()
      expect(onClick).not.toHaveBeenCalled()
    })
  })

  describe('State reset behavior', () => {
    it('should reset hasMoved state on each touch start', () => {
      const onLongPress = vi.fn()
      const onClick = vi.fn()
      const { result } = renderHook(() =>
        useLongPress(onLongPress, onClick, { delay: 500 })
      )

      // First interaction: scroll
      act(() => {
        fireTouchEvent(result.current, 'touchstart', 100, 100)
        fireTouchEvent(result.current, 'touchmove', 100, 120)
        fireTouchEvent(result.current, 'touchend', 100, 120)
      })

      expect(onClick).not.toHaveBeenCalled()

      // Second interaction: quick tap (should work despite previous scroll)
      act(() => {
        fireTouchEvent(result.current, 'touchstart', 100, 100)
        fireTouchEvent(result.current, 'touchend', 100, 100)
      })

      expect(onClick).toHaveBeenCalledOnce()
    })

    it('should reset isLongPressTriggered on each touch start', () => {
      const onLongPress = vi.fn()
      const onClick = vi.fn()
      const { result } = renderHook(() =>
        useLongPress(onLongPress, onClick, { delay: 500 })
      )

      // First interaction: long press
      act(() => {
        fireTouchEvent(result.current, 'touchstart', 100, 100)
        vi.advanceTimersByTime(500)
        fireTouchEvent(result.current, 'touchend', 100, 100)
      })

      expect(onLongPress).toHaveBeenCalledOnce()
      expect(onClick).not.toHaveBeenCalled()

      // Second interaction: quick tap (should work despite previous long press)
      act(() => {
        fireTouchEvent(result.current, 'touchstart', 100, 100)
        fireTouchEvent(result.current, 'touchend', 100, 100)
      })

      expect(onClick).toHaveBeenCalledOnce()
    })
  })

  describe('Edge cases', () => {
    it('should ignore non-left mouse button on mousedown', () => {
      const onLongPress = vi.fn()
      const onClick = vi.fn()
      const { result } = renderHook(() =>
        useLongPress(onLongPress, onClick, { delay: 500 })
      )

      const downEvent = {
        button: 1, // Middle button
        clientX: 100,
        clientY: 100,
        target: document.createElement('div'),
        preventDefault: vi.fn(),
      } as unknown as React.MouseEvent

      const upEvent = {
        button: 0, // Left button on up
        clientX: 100,
        clientY: 100,
        target: document.createElement('div'),
        preventDefault: vi.fn(),
      } as unknown as React.MouseEvent

      act(() => {
        result.current.onMouseDown(downEvent) // Should be ignored
        result.current.onMouseUp(upEvent) // Should not trigger onClick since start was ignored
      })

      expect(onClick).not.toHaveBeenCalled()
      expect(onLongPress).not.toHaveBeenCalled()
    })

    it('should handle multiple touchmove events correctly', () => {
      const onLongPress = vi.fn()
      const onClick = vi.fn()
      const { result } = renderHook(() =>
        useLongPress(onLongPress, onClick, { delay: 500 })
      )

      act(() => {
        fireTouchEvent(result.current, 'touchstart', 100, 100)
        fireTouchEvent(result.current, 'touchmove', 105, 105) // 7px - still ok
        fireTouchEvent(result.current, 'touchmove', 108, 108) // 11px total - exceeds threshold
        fireTouchEvent(result.current, 'touchmove', 120, 120) // Continue moving
        fireTouchEvent(result.current, 'touchend', 120, 120)
      })

      expect(onClick).not.toHaveBeenCalled()
      expect(onLongPress).not.toHaveBeenCalled()
    })

    it('should continue tracking movement after timer is cleared', () => {
      const onLongPress = vi.fn()
      const onClick = vi.fn()
      const { result } = renderHook(() =>
        useLongPress(onLongPress, onClick, { delay: 500 })
      )

      act(() => {
        fireTouchEvent(result.current, 'touchstart', 100, 100)
        fireTouchEvent(result.current, 'touchmove', 105, 105) // Small move, timer still active
        fireTouchEvent(result.current, 'touchmove', 120, 120) // Large move, timer cleared
        // Continue moving after timer cleared - should still track
        fireTouchEvent(result.current, 'touchmove', 130, 130)
        fireTouchEvent(result.current, 'touchend', 130, 130)
      })

      expect(onClick).not.toHaveBeenCalled()
      expect(onLongPress).not.toHaveBeenCalled()
    })
  })
})
