import { useRef, useCallback } from 'react';

interface UseLongPressOptions {
  isPreventDefault?: boolean;
  delay?: number;
}

export function useLongPress(
  onLongPress: (e: React.TouchEvent | React.MouseEvent) => void,
  onClick: (e: React.TouchEvent | React.MouseEvent) => void,
  { isPreventDefault = true, delay = 500 }: UseLongPressOptions = {}
) {
  const timeout = useRef<NodeJS.Timeout | null>(null);
  const target = useRef<EventTarget | null>(null);
  const isLongPressTriggered = useRef(false);
  // To handle move tolerance
  const startPos = useRef<{ x: number, y: number } | null>(null);
  const hasMoved = useRef(false);

  const start = useCallback(
    (event: React.TouchEvent | React.MouseEvent) => {
      // Only handle left click or touch
      if ('button' in event && event.button !== 0) return;

      if (isPreventDefault && event.target) {
        event.target.addEventListener(
          'touchend',
          preventDefault,
          { passive: false }
        );
        target.current = event.target;
      }

      isLongPressTriggered.current = false;
      hasMoved.current = false;

      // Record start position
      if ('touches' in event) {
          startPos.current = { x: event.touches[0].clientX, y: event.touches[0].clientY };
      } else {
          startPos.current = { x: (event as React.MouseEvent).clientX, y: (event as React.MouseEvent).clientY };
      }

      timeout.current = setTimeout(() => {
        onLongPress(event);
        isLongPressTriggered.current = true;
        // Haptic feedback
        if (typeof navigator !== 'undefined' && navigator.vibrate) {
            navigator.vibrate(10);
        }
      }, delay);
    },
    [onLongPress, delay, isPreventDefault]
  );

  const clear = useCallback(
    (event: React.TouchEvent | React.MouseEvent, shouldTriggerClick = true) => {
      if (timeout.current) {
        clearTimeout(timeout.current);
        timeout.current = null;
      }

      // If long press hasn't triggered yet, and we should trigger click (i.e. not moved too much)
      // Also check startPos exists to ensure start was actually called (handles non-left button case)
      if (shouldTriggerClick && !isLongPressTriggered.current && !hasMoved.current && startPos.current) {
        onClick(event);
      }

      isLongPressTriggered.current = false;
      startPos.current = null;

      if (isPreventDefault && target.current) {
        target.current.removeEventListener('touchend', preventDefault);
      }
    },
    [isPreventDefault, onClick]
  );

  const move = useCallback(
      (event: React.TouchEvent | React.MouseEvent) => {
          if (!startPos.current) return;
          
          let clientX, clientY;
          if ('touches' in event) {
              clientX = event.touches[0].clientX;
              clientY = event.touches[0].clientY;
          } else {
              clientX = (event as React.MouseEvent).clientX;
              clientY = (event as React.MouseEvent).clientY;
          }
          
          const diffX = Math.abs(clientX - startPos.current.x);
          const diffY = Math.abs(clientY - startPos.current.y);

          // If moved more than 10px, cancel long press and mark as scroll gesture
          // 10px threshold balances tap accuracy with scroll sensitivity
          if (diffX > 10 || diffY > 10) {
              hasMoved.current = true;
              if (timeout.current) {
                  clearTimeout(timeout.current);
                  timeout.current = null;
              }
          }
      },
      []
  );

  return {
    onMouseDown: (e: React.MouseEvent) => start(e),
    onTouchStart: (e: React.TouchEvent) => start(e),
    onMouseUp: (e: React.MouseEvent) => clear(e),
    onMouseLeave: (e: React.MouseEvent) => clear(e, false),
    onTouchEnd: (e: React.TouchEvent) => clear(e),
    onMouseMove: (e: React.MouseEvent) => move(e),
    onTouchMove: (e: React.TouchEvent) => move(e),
  };
}

const preventDefault = (event: Event) => {
  if (!('touches' in event)) return;
  if (event instanceof TouchEvent && event.touches.length < 2) {
    // We only prevent default if we want to stop scroll on long press? 
    // Actually blocking scroll is tricky. Usually we don't want to block scroll unless we are sure.
    // Let's keep it simple: we don't preventDefault here for now to allow scrolling.
    // If we want to prevent context menu:
    // event.preventDefault();
  }
};
