import { describe, it, expect, vi } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import { ActionSheet } from '@/components/ActionSheet'

const mockActions = [
  { label: '设为管理员', onPress: vi.fn() },
  { label: '禁用账户', variant: 'destructive' as const, onPress: vi.fn() },
]

describe('ActionSheet', () => {
  it('should not render when closed', () => {
    render(
      <ActionSheet isOpen={false} actions={mockActions} onClose={vi.fn()} />
    )

    expect(screen.queryByText('设为管理员')).not.toBeInTheDocument()
    expect(screen.queryByText('取消')).not.toBeInTheDocument()
  })

  it('should render actions and cancel button when open', () => {
    render(
      <ActionSheet isOpen={true} actions={mockActions} onClose={vi.fn()} />
    )

    expect(screen.getByText('设为管理员')).toBeInTheDocument()
    expect(screen.getByText('禁用账户')).toBeInTheDocument()
    expect(screen.getByText('取消')).toBeInTheDocument()
  })

  it('should render title when provided', () => {
    render(
      <ActionSheet
        isOpen={true}
        title="user1 的操作"
        actions={mockActions}
        onClose={vi.fn()}
      />
    )

    expect(screen.getByText('user1 的操作')).toBeInTheDocument()
  })

  it('should call onPress and onClose when action is clicked', async () => {
    const onClose = vi.fn()
    const onPress = vi.fn()
    const actions = [{ label: '测试操作', onPress }]

    render(
      <ActionSheet isOpen={true} actions={actions} onClose={onClose} />
    )

    await act(async () => {
      screen.getByText('测试操作').click()
    })

    expect(onPress).toHaveBeenCalledOnce()
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('should call onClose when cancel is clicked', async () => {
    const onClose = vi.fn()

    render(
      <ActionSheet isOpen={true} actions={mockActions} onClose={onClose} />
    )

    await act(async () => {
      screen.getByText('取消').click()
    })

    expect(onClose).toHaveBeenCalledOnce()
  })

  it('should set body overflow hidden when open', () => {
    render(
      <ActionSheet isOpen={true} actions={mockActions} onClose={vi.fn()} />
    )

    expect(document.body.style.overflow).toBe('hidden')
  })

  it('should restore body overflow when closed', () => {
    const { rerender } = render(
      <ActionSheet isOpen={true} actions={mockActions} onClose={vi.fn()} />
    )

    expect(document.body.style.overflow).toBe('hidden')

    rerender(
      <ActionSheet isOpen={false} actions={mockActions} onClose={vi.fn()} />
    )

    expect(document.body.style.overflow).toBe('unset')
  })
})
