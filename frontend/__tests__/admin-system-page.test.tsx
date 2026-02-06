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

const mockFetchSystemConfig = vi.fn()
const mockSetRegistrationEnabled = vi.fn()
const mockSetMaxWatchlistItems = vi.fn()

vi.mock('@/lib/api', () => ({
  fetchSystemConfig: (...args: any[]) => mockFetchSystemConfig(...args),
  setRegistrationEnabled: (...args: any[]) => mockSetRegistrationEnabled(...args),
  setMaxWatchlistItems: (...args: any[]) => mockSetMaxWatchlistItems(...args),
}))

let mockAuthValue: any

vi.mock('@/lib/auth-context', () => ({
  useAuth: () => mockAuthValue,
}))

import SystemConfigPage from '@/app/admin/system/page'

const defaultConfig = { registration_enabled: true, max_watchlist_items: 100 }

beforeEach(() => {
  mockPush.mockReset()
  mockToast.mockReset()
  mockFetchSystemConfig.mockReset()
  mockSetRegistrationEnabled.mockReset()
  mockSetMaxWatchlistItems.mockReset()
  mockAuthValue = {
    user: { id: 1, username: 'admin', is_admin: true, is_active: true },
    token: 'test-token',
    isLoading: false,
  }
})

describe('SystemConfigPage', () => {
  describe('Auth guard', () => {
    it('should redirect non-admin to home', () => {
      mockAuthValue = {
        ...mockAuthValue,
        user: { id: 2, username: 'user', is_admin: false, is_active: true },
      }
      render(<SystemConfigPage />)
      expect(mockPush).toHaveBeenCalledWith('/')
    })

    it('should render null when loading', () => {
      mockFetchSystemConfig.mockResolvedValue(defaultConfig)
      mockAuthValue = { ...mockAuthValue, isLoading: true }
      const { container } = render(<SystemConfigPage />)
      expect(container.innerHTML).toBe('')
    })
  })

  describe('Data loading', () => {
    it('should display config after loading', async () => {
      mockFetchSystemConfig.mockResolvedValue(defaultConfig)

      render(<SystemConfigPage />)

      await waitFor(() => {
        expect(screen.getByText('开放注册')).toBeInTheDocument()
        expect(screen.getByText('自选上限')).toBeInTheDocument()
        expect(screen.getByDisplayValue('100')).toBeInTheDocument()
      })
    })

    it('should show toast on fetch error', async () => {
      mockFetchSystemConfig.mockRejectedValue(new Error('fail'))

      render(<SystemConfigPage />)

      await waitFor(() => {
        expect(mockToast).toHaveBeenCalledWith('获取系统配置失败', 'error')
      })
    })
  })

  describe('Registration toggle', () => {
    it('should call API and show success toast on toggle', async () => {
      mockFetchSystemConfig.mockResolvedValue(defaultConfig)
      mockSetRegistrationEnabled.mockResolvedValue({ registration_enabled: false })

      render(<SystemConfigPage />)

      await waitFor(() => {
        expect(screen.getByText('开放注册')).toBeInTheDocument()
      })

      // Find the toggle button (the one with rounded-full class inside)
      const toggleButton = screen.getByText('开放注册')
        .closest('div')!
        .querySelector('button')!

      await act(async () => {
        toggleButton.click()
      })

      await waitFor(() => {
        expect(mockSetRegistrationEnabled).toHaveBeenCalledWith('test-token', false)
        expect(mockToast).toHaveBeenCalledWith('已关闭注册', 'success')
      })
    })

    it('should rollback and show error toast on API failure', async () => {
      mockFetchSystemConfig.mockResolvedValue(defaultConfig)
      mockSetRegistrationEnabled.mockRejectedValue(new Error('网络错误'))

      render(<SystemConfigPage />)

      await waitFor(() => {
        expect(screen.getByText('开放注册')).toBeInTheDocument()
      })

      const toggleButton = screen.getByText('开放注册')
        .closest('div')!
        .querySelector('button')!

      await act(async () => {
        toggleButton.click()
      })

      await waitFor(() => {
        expect(mockToast).toHaveBeenCalledWith('网络错误', 'error')
      })
    })
  })

  describe('Max watchlist items', () => {
    it('should call API when select value changes', async () => {
      mockFetchSystemConfig.mockResolvedValue(defaultConfig)
      mockSetMaxWatchlistItems.mockResolvedValue({ max_watchlist_items: 200 })

      render(<SystemConfigPage />)

      await waitFor(() => {
        expect(screen.getByDisplayValue('100')).toBeInTheDocument()
      })

      const select = screen.getByDisplayValue('100') as HTMLSelectElement

      await act(async () => {
        select.value = '200'
        select.dispatchEvent(new Event('change', { bubbles: true }))
      })

      await waitFor(() => {
        expect(mockSetMaxWatchlistItems).toHaveBeenCalledWith('test-token', 200)
        expect(mockToast).toHaveBeenCalledWith('自选上限已设为 200', 'success')
      })
    })

    it('should rollback on API failure', async () => {
      mockFetchSystemConfig.mockResolvedValue(defaultConfig)
      mockSetMaxWatchlistItems.mockRejectedValue(new Error('操作失败'))

      render(<SystemConfigPage />)

      await waitFor(() => {
        expect(screen.getByDisplayValue('100')).toBeInTheDocument()
      })

      const select = screen.getByDisplayValue('100') as HTMLSelectElement

      await act(async () => {
        select.value = '500'
        select.dispatchEvent(new Event('change', { bubbles: true }))
      })

      await waitFor(() => {
        expect(mockToast).toHaveBeenCalledWith('操作失败', 'error')
        // After rollback, select should show original value
        expect(screen.getByDisplayValue('100')).toBeInTheDocument()
      })
    })
  })
})
