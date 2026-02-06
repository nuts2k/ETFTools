import { useEffect, useState, useRef, useCallback } from 'react';

export type PullState = 'idle' | 'pulling' | 'threshold' | 'refreshing' | 'complete';

interface UsePullToRefreshOptions {
  onRefresh: () => Promise<void>;
  scrollRef: React.RefObject<HTMLElement | null>;
  threshold?: number;
  maxPull?: number;
  cooldown?: number;
  disabled?: boolean;
}

interface UsePullToRefreshReturn {
  pullDistance: number;
  state: PullState;
}

const DIRECTION_LOCK_DISTANCE = 10;
const REFRESH_TIMEOUT_MS = 15000;
const COMPLETE_DISPLAY_MS = 400;

export function usePullToRefresh({
  onRefresh,
  scrollRef,
  threshold = 80,
  maxPull = 120,
  cooldown = 3000,
  disabled = false,
}: UsePullToRefreshOptions): UsePullToRefreshReturn {
  const [pullDistance, setPullDistance] = useState(0);
  const [state, setState] = useState<PullState>('idle');

  // Refs to avoid stale closures in native event handlers
  const currentState = useRef<PullState>('idle');
  const pullDistanceRef = useRef(0);
  const startY = useRef(0);
  const startX = useRef(0);
  const directionLocked = useRef<'vertical' | 'horizontal' | null>(null);
  const lastRefreshTime = useRef(0);
  const onRefreshRef = useRef(onRefresh);

  // Keep onRefresh ref up to date
  useEffect(() => {
    onRefreshRef.current = onRefresh;
  }, [onRefresh]);

  const updateState = useCallback((newState: PullState) => {
    currentState.current = newState;
    setState(newState);
  }, []);

  const updatePullDistance = useCallback((distance: number) => {
    pullDistanceRef.current = distance;
    setPullDistance(distance);
  }, []);

  const resetPull = useCallback(() => {
    updatePullDistance(0);
    updateState('idle');
  }, [updatePullDistance, updateState]);

  const executeRefresh = useCallback(async () => {
    updateState('refreshing');

    let timeoutId: ReturnType<typeof setTimeout>;
    const timeoutPromise = new Promise<never>((_, reject) => {
      timeoutId = setTimeout(() => reject(new Error('Refresh timeout')), REFRESH_TIMEOUT_MS);
    });

    try {
      await Promise.race([onRefreshRef.current(), timeoutPromise]);
    } catch {
      // Swallow error; state resets in finally
    } finally {
      clearTimeout(timeoutId!);
      lastRefreshTime.current = Date.now();
      updatePullDistance(0);
      updateState('complete');

      setTimeout(() => {
        // Only transition to idle if still in complete state
        if (currentState.current === 'complete') {
          updateState('idle');
        }
      }, COMPLETE_DISPLAY_MS);
    }
  }, [updateState, updatePullDistance]);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el || disabled) return;

    const handleTouchStart = (e: TouchEvent) => {
      if (currentState.current === 'refreshing' || currentState.current === 'complete') return;

      // Cooldown check
      if (Date.now() - lastRefreshTime.current < cooldown) return;

      // iOS Safari reports fractional scrollTop (e.g. 0.33, 0.5) even when
      // visually at top. 1px tolerance covers these; imperceptible to users.
      if (el.scrollTop > 1) return;

      const touch = e.touches[0];
      startY.current = touch.clientY;
      startX.current = touch.clientX;
      directionLocked.current = null;
    };

    const handleTouchMove = (e: TouchEvent) => {
      if (currentState.current === 'refreshing' || currentState.current === 'complete') return;

      // Late activation: if touchstart was skipped (scrollTop wasn't 0 yet),
      // capture the start position now once we've scrolled to top
      if (startY.current === 0 && startX.current === 0) {
        if (el.scrollTop <= 1) {
          const touch = e.touches[0];
          startY.current = touch.clientY;
          startX.current = touch.clientX;
          directionLocked.current = null;
        }
        return;
      }

      const touch = e.touches[0];
      const deltaY = touch.clientY - startY.current;
      const deltaX = touch.clientX - startX.current;

      // Direction lock: determine after 10px of movement
      if (directionLocked.current === null) {
        const absDeltaY = Math.abs(deltaY);
        const absDeltaX = Math.abs(deltaX);

        if (absDeltaX > DIRECTION_LOCK_DISTANCE || absDeltaY > DIRECTION_LOCK_DISTANCE) {
          directionLocked.current = absDeltaX > absDeltaY ? 'horizontal' : 'vertical';
        }

        if (directionLocked.current !== 'vertical') return;
      }

      // Abort if horizontal scroll was detected first
      if (directionLocked.current === 'horizontal') return;

      // Only handle downward pull
      if (deltaY <= 0) {
        if (currentState.current === 'pulling' || currentState.current === 'threshold') {
          resetPull();
        }
        return;
      }

      // Block native pull-to-refresh
      e.preventDefault();

      // Monotonic resistance curve: resisted = maxPull * (1 - e^(-deltaY/k))
      // k is chosen so that resisted == threshold when deltaY == threshold
      const ratio = threshold / maxPull;
      const k = ratio >= 1
        ? maxPull
        : -threshold / Math.log(1 - ratio);
      const resistedDelta = maxPull * (1 - Math.exp(-deltaY / k));
      const clampedDistance = Math.min(resistedDelta, maxPull);

      updatePullDistance(clampedDistance);

      const prevState = currentState.current;

      if (clampedDistance >= threshold) {
        if (prevState !== 'threshold') {
          updateState('threshold');
          // Haptic feedback when crossing threshold
          if (typeof navigator !== 'undefined' && navigator.vibrate) {
            navigator.vibrate(10);
          }
        }
      } else if (clampedDistance > 0) {
        if (prevState !== 'pulling') {
          updateState('pulling');
        }
      }
    };

    const handleTouchEnd = () => {
      if (currentState.current === 'refreshing' || currentState.current === 'complete') return;

      if (currentState.current === 'threshold') {
        executeRefresh();
      } else {
        resetPull();
      }

      // Reset touch tracking
      startY.current = 0;
      startX.current = 0;
      directionLocked.current = null;
    };

    el.addEventListener('touchstart', handleTouchStart, { passive: true });
    el.addEventListener('touchmove', handleTouchMove, { passive: false });
    el.addEventListener('touchend', handleTouchEnd, { passive: true });

    return () => {
      el.removeEventListener('touchstart', handleTouchStart);
      el.removeEventListener('touchmove', handleTouchMove);
      el.removeEventListener('touchend', handleTouchEnd);
    };
  }, [
    scrollRef,
    disabled,
    threshold,
    maxPull,
    cooldown,
    updateState,
    updatePullDistance,
    resetPull,
    executeRefresh,
  ]);

  return { pullDistance, state };
}
