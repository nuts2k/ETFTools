import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import { ToastProvider, useToast } from '@/components/Toast'

function TestConsumer() {
  const { toast } = useToast()
  return (
    <div>
      <button onClick={() => toast("成功消息", "success")}>show-success</button>
      <button onClick={() => toast("错误消息", "error")}>show-error</button>
      <button onClick={() => toast("替换消息", "success")}>show-replace</button>
    </div>
  )
}

function renderWithProvider() {
  return render(
    <ToastProvider>
      <TestConsumer />
    </ToastProvider>
  )
}

describe('Toast', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('should throw when useToast is used outside provider', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(() => render(<TestConsumer />)).toThrow(
      'useToast must be used within a ToastProvider'
    )
    spy.mockRestore()
  })

  it('should show success toast', async () => {
    renderWithProvider()

    await act(async () => {
      screen.getByText('show-success').click()
    })

    expect(screen.getByText('成功消息')).toBeInTheDocument()
  })

  it('should show error toast', async () => {
    renderWithProvider()

    await act(async () => {
      screen.getByText('show-error').click()
    })

    expect(screen.getByText('错误消息')).toBeInTheDocument()
  })

  it('should auto-dismiss after 2500ms', async () => {
    renderWithProvider()

    await act(async () => {
      screen.getByText('show-success').click()
    })

    expect(screen.getByText('成功消息')).toBeInTheDocument()

    await act(async () => {
      vi.advanceTimersByTime(2500)
    })

    expect(screen.queryByText('成功消息')).not.toBeInTheDocument()
  })

  it('should replace old toast with new one', async () => {
    renderWithProvider()

    await act(async () => {
      screen.getByText('show-success').click()
    })

    expect(screen.getByText('成功消息')).toBeInTheDocument()

    await act(async () => {
      screen.getByText('show-replace').click()
    })

    expect(screen.queryByText('成功消息')).not.toBeInTheDocument()
    expect(screen.getByText('替换消息')).toBeInTheDocument()
  })
})
