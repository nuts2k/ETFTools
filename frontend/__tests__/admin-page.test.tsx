import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import React from 'react'

// --- Mocks ---
const mockPush = vi.fn()
const mockToast = vi.fn()

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}))

vi.mock('next/link', () => ({
  default: ({ href, children, ...props }: any) => (
    <a href={href} {...props}>{children}</a>
  ),
}))

vi.mock('@/components/Toast', () => ({
  useToast: () => ({ toast: mockToast }),
  ToastProvider: ({ children }: any) => <>{children}</>,
}))

const mockFetchAdminUsers = vi.fn()
const mockFetchSystemConfig = vi.fn()

vi.mock('@/lib/api', () => ({
  fetchAdminUsers: (...args: any[]) => mockFetchAdminUsers(...args),
  fetchSystemConfig: (...args: any[]) => mockFetchSystemConfig(...args),
}))

let mockAuthValue = {
  user: { id: 1, username: 'admin', is_admin: true, is_active: true } as any,
  token: 'test-token' as string | null,
  isLoading: false,
}

vi.mock('@/lib/auth-context', () => ({
  useAuth: () => mockAuthValue,
}))

import AdminPage from '@/app/admin/page'

beforeEach(() => {
  mockPush.mockReset()
  mockToast.mockReset()
  mockFetchAdminUsers.mockReset()
  mockFetchSystemConfig.mockReset()
  mockAuthValue = {
    user: { id: 1, username: 'admin', is_admin: true, is_active: true },
    token: 'test-token',
    isLoading: false,
  }
})

describe('AdminPage', () => {
  describe('Auth guard', () => {
    it('should render null when loading', () => {
      mockAuthValue = { ...mockAuthValue, isLoading: true }
      const { container } = render(<AdminPage />)
      expect(container.innerHTML).toBe('')
    })

    it('should redirect non-admin to home', () => {
      mockAuthValue = {
        ...mockAuthValue,
        user: { id: 2, username: 'user', is_admin: false, is_active: true },
      }
      render(<AdminPage />)
      expect(mockPush).toHaveBeenCalledWith('/')
    })

    it('should render null for non-admin user', () => {
      mockAuthValue = {
        ...mockAuthValue,
        user: { id: 2, username: 'user', is_admin: false, is_active: true },
      }
      const { container } = render(<AdminPage />)
      expect(container.innerHTML).toBe('')
    })
  })

  describe('Data loading', () => {
    it('should fetch users and config on mount', () => {
      mockFetchAdminUsers.mockResolvedValue([])
      mockFetchSystemConfig.mockResolvedValue({
        registration_enabled: true,
        max_watchlist_items: 100,
      })

      render(<AdminPage />)

      expect(mockFetchAdminUsers).toHaveBeenCalledWith('test-token')
      expect(mockFetchSystemConfig).toHaveBeenCalledWith('test-token')
    })

    it('should display stats after data loads', async () => {
      mockFetchAdminUsers.mockResolvedValue([
        { id: 1, username: 'admin', is_admin: true, is_active: true },
        { id: 2, username: 'user1', is_admin: false, is_active: true },
        { id: 3, username: 'user2', is_admin: false, is_active: true },
      ])
      mockFetchSystemConfig.mockResolvedValue({
        registration_enabled: true,
        max_watchlist_items: 100,
      })

      render(<AdminPage />)

      await waitFor(() => {
        expect(screen.getByText('3')).toBeInTheDocument() // user count
        expect(screen.getByText('1')).toBeInTheDocument() // admin count
        expect(screen.getByText('开放')).toBeInTheDocument()
        expect(screen.getByText('100')).toBeInTheDocument()
      })
    })

    it('should show toast on fetch error', async () => {
      mockFetchAdminUsers.mockRejectedValue(new Error('fail'))
      mockFetchSystemConfig.mockRejectedValue(new Error('fail'))

      render(<AdminPage />)

      await waitFor(() => {
        expect(mockToast).toHaveBeenCalledWith('加载管理数据失败', 'error')
      })
    })

    it('should not fetch when token is null', () => {
      mockAuthValue = { ...mockAuthValue, token: null }
      mockFetchAdminUsers.mockResolvedValue([])
      mockFetchSystemConfig.mockResolvedValue({})

      render(<AdminPage />)

      expect(mockFetchAdminUsers).not.toHaveBeenCalled()
      expect(mockFetchSystemConfig).not.toHaveBeenCalled()
    })
  })

  describe('Navigation', () => {
    it('should render navigation links', () => {
      mockFetchAdminUsers.mockResolvedValue([])
      mockFetchSystemConfig.mockResolvedValue({
        registration_enabled: true,
        max_watchlist_items: 100,
      })

      render(<AdminPage />)

      const usersLink = screen.getByText('用户管理').closest('a')
      const systemLink = screen.getByText('系统设置').closest('a')
      expect(usersLink).toHaveAttribute('href', '/admin/users')
      expect(systemLink).toHaveAttribute('href', '/admin/system')
    })

    it('should render page title', () => {
      mockFetchAdminUsers.mockResolvedValue([])
      mockFetchSystemConfig.mockResolvedValue({})

      render(<AdminPage />)

      expect(screen.getByText('管理员控制台')).toBeInTheDocument()
    })
  })
})
