import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import React from 'react'

// --- Mocks ---
const mockPush = vi.fn()
const mockToast = vi.fn()

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}))

vi.mock('@/components/Toast', () => ({
  useToast: () => ({ toast: mockToast }),
}))

const mockFetchAdminUsers = vi.fn()
const mockToggleUserAdmin = vi.fn()
const mockToggleUserActive = vi.fn()

vi.mock('@/lib/api', () => ({
  fetchAdminUsers: (...args: any[]) => mockFetchAdminUsers(...args),
  toggleUserAdmin: (...args: any[]) => mockToggleUserAdmin(...args),
  toggleUserActive: (...args: any[]) => mockToggleUserActive(...args),
}))

vi.mock('@/components/ActionSheet', () => ({
  ActionSheet: ({ isOpen, title, actions, onClose }: any) => {
    if (!isOpen) return null
    return (
      <div data-testid="action-sheet">
        {title && <div>{title}</div>}
        {actions.map((a: any, i: number) => (
          <button key={i} onClick={() => { a.onPress(); onClose() }}>
            {a.label}
          </button>
        ))}
        <button onClick={onClose}>取消</button>
      </div>
    )
  },
}))

vi.mock('@/components/ConfirmationDialog', () => ({
  ConfirmationDialog: ({ isOpen, title, onConfirm, onCancel }: any) => {
    if (!isOpen) return null
    return (
      <div data-testid="confirm-dialog">
        <div>{title}</div>
        <button onClick={onConfirm}>确认</button>
        <button onClick={onCancel}>取消确认</button>
      </div>
    )
  },
}))

let mockAuthValue: any

vi.mock('@/lib/auth-context', () => ({
  useAuth: () => mockAuthValue,
}))

import UsersPage from '@/app/admin/users/page'

const adminUser = { id: 1, username: 'admin', is_admin: true, is_active: true, created_at: '2026-01-15T00:00:00Z', settings: {} }
const normalUser = { id: 2, username: 'user1', is_admin: false, is_active: true, created_at: '2026-01-20T00:00:00Z', settings: {} }
const disabledUser = { id: 3, username: 'user2', is_admin: false, is_active: false, created_at: '2026-02-01T00:00:00Z', settings: {} }

beforeEach(() => {
  mockPush.mockReset()
  mockToast.mockReset()
  mockFetchAdminUsers.mockReset()
  mockToggleUserAdmin.mockReset()
  mockToggleUserActive.mockReset()
  mockAuthValue = {
    user: { id: 1, username: 'admin', is_admin: true, is_active: true },
    token: 'test-token',
    isLoading: false,
  }
})

describe('UsersPage', () => {
  describe('Auth guard', () => {
    it('should redirect non-admin to home', () => {
      mockAuthValue = {
        ...mockAuthValue,
        user: { id: 2, username: 'user', is_admin: false, is_active: true },
      }
      render(<UsersPage />)
      expect(mockPush).toHaveBeenCalledWith('/')
    })

    it('should render null when loading', () => {
      mockAuthValue = { ...mockAuthValue, isLoading: true }
      const { container } = render(<UsersPage />)
      expect(container.innerHTML).toBe('')
    })
  })

  describe('User list', () => {
    it('should display users after loading', async () => {
      mockFetchAdminUsers.mockResolvedValue([adminUser, normalUser, disabledUser])

      render(<UsersPage />)

      await waitFor(() => {
        expect(screen.getByText('admin')).toBeInTheDocument()
        expect(screen.getByText('user1')).toBeInTheDocument()
        expect(screen.getByText('user2')).toBeInTheDocument()
      })
    })

    it('should show empty state when no users', async () => {
      mockFetchAdminUsers.mockResolvedValue([])

      render(<UsersPage />)

      await waitFor(() => {
        expect(screen.getByText('暂无用户')).toBeInTheDocument()
      })
    })

    it('should show toast on fetch error', async () => {
      mockFetchAdminUsers.mockRejectedValue(new Error('fail'))

      render(<UsersPage />)

      await waitFor(() => {
        expect(mockToast).toHaveBeenCalledWith('获取用户列表失败', 'error')
      })
    })

    it('should display status badges', async () => {
      mockFetchAdminUsers.mockResolvedValue([adminUser, normalUser, disabledUser])

      render(<UsersPage />)

      await waitFor(() => {
        // "管理员" and "已禁用" appear in both tabs and badges, use selector to check badges
        const badges = document.querySelectorAll('span.rounded-full')
        const badgeTexts = Array.from(badges).map(b => b.textContent)
        expect(badgeTexts).toContain('管理员')
        expect(badgeTexts).toContain('正常')
        expect(badgeTexts).toContain('已禁用')
      })
    })
  })

  describe('Self-protection', () => {
    it('should show toast when clicking own user row', async () => {
      mockFetchAdminUsers.mockResolvedValue([adminUser, normalUser])

      render(<UsersPage />)

      await waitFor(() => {
        expect(screen.getByText('admin')).toBeInTheDocument()
      })

      await act(async () => {
        screen.getByText('admin').closest('button')!.click()
      })

      expect(mockToast).toHaveBeenCalledWith('无法修改自己的权限', 'error')
      expect(screen.queryByTestId('action-sheet')).not.toBeInTheDocument()
    })
  })

  describe('ActionSheet + ConfirmationDialog flow', () => {
    it('should open ActionSheet when clicking another user', async () => {
      mockFetchAdminUsers.mockResolvedValue([adminUser, normalUser])

      render(<UsersPage />)

      await waitFor(() => {
        expect(screen.getByText('user1')).toBeInTheDocument()
      })

      await act(async () => {
        screen.getByText('user1').closest('button')!.click()
      })

      expect(screen.getByTestId('action-sheet')).toBeInTheDocument()
      expect(screen.getByText('user1 的操作')).toBeInTheDocument()
    })

    it('should show ConfirmationDialog after selecting action', async () => {
      mockFetchAdminUsers.mockResolvedValue([adminUser, normalUser])

      render(<UsersPage />)

      await waitFor(() => {
        expect(screen.getByText('user1')).toBeInTheDocument()
      })

      // Open ActionSheet
      await act(async () => {
        screen.getByText('user1').closest('button')!.click()
      })

      // Select "设为管理员"
      await act(async () => {
        screen.getByText('设为管理员').click()
      })

      expect(screen.getByTestId('confirm-dialog')).toBeInTheDocument()
      expect(screen.getByText('授予管理员权限')).toBeInTheDocument()
    })
  })

  describe('Optimistic update', () => {
    it('should toggle admin and show success toast', async () => {
      mockFetchAdminUsers.mockResolvedValue([adminUser, normalUser])
      mockToggleUserAdmin.mockResolvedValue({ user_id: 2, is_admin: true })

      render(<UsersPage />)

      await waitFor(() => {
        expect(screen.getByText('user1')).toBeInTheDocument()
      })

      // Open ActionSheet → select action → confirm
      await act(async () => {
        screen.getByText('user1').closest('button')!.click()
      })
      await act(async () => {
        screen.getByText('设为管理员').click()
      })
      await act(async () => {
        screen.getByText('确认').click()
      })

      await waitFor(() => {
        expect(mockToggleUserAdmin).toHaveBeenCalledWith('test-token', 2)
        expect(mockToast).toHaveBeenCalledWith('已将 user1 设为管理员', 'success')
      })
    })

    it('should rollback on API error', async () => {
      mockFetchAdminUsers.mockResolvedValue([adminUser, normalUser])
      mockToggleUserAdmin.mockRejectedValue(new Error('服务器错误'))

      render(<UsersPage />)

      await waitFor(() => {
        expect(screen.getByText('user1')).toBeInTheDocument()
      })

      await act(async () => {
        screen.getByText('user1').closest('button')!.click()
      })
      await act(async () => {
        screen.getByText('设为管理员').click()
      })
      await act(async () => {
        screen.getByText('确认').click()
      })

      await waitFor(() => {
        expect(mockToast).toHaveBeenCalledWith('服务器错误', 'error')
      })

      // Badge should still show "正常" after rollback
      expect(screen.getByText('正常')).toBeInTheDocument()
    })
  })

  describe('Filter tabs', () => {
    it('should render filter tabs', () => {
      mockFetchAdminUsers.mockResolvedValue([])

      render(<UsersPage />)

      expect(screen.getByText('全部')).toBeInTheDocument()
      expect(screen.getByText('管理员')).toBeInTheDocument()
      expect(screen.getByText('已禁用')).toBeInTheDocument()
    })

    it('should refetch with filter params when tab changes', async () => {
      mockFetchAdminUsers.mockResolvedValue([adminUser, normalUser])

      render(<UsersPage />)

      await waitFor(() => {
        expect(mockFetchAdminUsers).toHaveBeenCalledWith('test-token', {})
      })

      mockFetchAdminUsers.mockResolvedValue([adminUser])

      // Click the tab button (not the badge) — tabs are in a flex container with gap-2
      const tabContainer = screen.getByText('全部').parentElement!
      const adminTab = Array.from(tabContainer.querySelectorAll('button'))
        .find(btn => btn.textContent === '管理员')!

      await act(async () => {
        adminTab.click()
      })

      await waitFor(() => {
        expect(mockFetchAdminUsers).toHaveBeenCalledWith('test-token', { is_admin: true })
      })
    })
  })
})
