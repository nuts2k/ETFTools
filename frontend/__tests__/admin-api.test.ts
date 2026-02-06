import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  fetchAdminUsers,
  toggleUserAdmin,
  toggleUserActive,
  fetchSystemConfig,
  setRegistrationEnabled,
  setMaxWatchlistItems,
} from '@/lib/api'

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

beforeEach(() => {
  mockFetch.mockReset()
})

const TOKEN = 'test-token'

function mockOk(data: unknown) {
  mockFetch.mockResolvedValueOnce({
    ok: true,
    json: () => Promise.resolve(data),
  })
}

function mockError(status: number, detail: string) {
  mockFetch.mockResolvedValueOnce({
    ok: false,
    json: () => Promise.resolve({ detail }),
  })
}

describe('fetchAdminUsers', () => {
  it('should fetch users with auth header', async () => {
    const users = [{ id: 1, username: 'admin', is_admin: true, is_active: true }]
    mockOk(users)

    const result = await fetchAdminUsers(TOKEN)

    expect(mockFetch).toHaveBeenCalledOnce()
    const [url, opts] = mockFetch.mock.calls[0]
    expect(url).toContain('/admin/users')
    expect(url).not.toContain('?')
    expect(opts.headers.Authorization).toBe('Bearer test-token')
    expect(result).toEqual(users)
  })

  it('should append is_admin query param', async () => {
    mockOk([])

    await fetchAdminUsers(TOKEN, { is_admin: true })

    const [url] = mockFetch.mock.calls[0]
    expect(url).toContain('is_admin=true')
  })

  it('should append is_active query param', async () => {
    mockOk([])

    await fetchAdminUsers(TOKEN, { is_active: false })

    const [url] = mockFetch.mock.calls[0]
    expect(url).toContain('is_active=false')
  })

  it('should append both query params', async () => {
    mockOk([])

    await fetchAdminUsers(TOKEN, { is_admin: true, is_active: false })

    const [url] = mockFetch.mock.calls[0]
    expect(url).toContain('is_admin=true')
    expect(url).toContain('is_active=false')
  })

  it('should throw on error response', async () => {
    mockError(403, '权限不足')

    await expect(fetchAdminUsers(TOKEN)).rejects.toThrow('权限不足')
  })

  it('should use fallback message when json parse fails', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: () => Promise.reject(new Error('parse error')),
    })

    await expect(fetchAdminUsers(TOKEN)).rejects.toThrow('获取用户列表失败')
  })
})

describe('toggleUserAdmin', () => {
  it('should POST to toggle-admin endpoint', async () => {
    mockOk({ user_id: 5, is_admin: true })

    const result = await toggleUserAdmin(TOKEN, 5)

    const [url, opts] = mockFetch.mock.calls[0]
    expect(url).toContain('/admin/users/5/toggle-admin')
    expect(opts.method).toBe('POST')
    expect(result).toEqual({ user_id: 5, is_admin: true })
  })

  it('should throw on error', async () => {
    mockError(400, '不能修改自己')

    await expect(toggleUserAdmin(TOKEN, 1)).rejects.toThrow('不能修改自己')
  })
})

describe('toggleUserActive', () => {
  it('should POST to toggle-active endpoint', async () => {
    mockOk({ user_id: 3, is_active: false })

    const result = await toggleUserActive(TOKEN, 3)

    const [url, opts] = mockFetch.mock.calls[0]
    expect(url).toContain('/admin/users/3/toggle-active')
    expect(opts.method).toBe('POST')
    expect(result).toEqual({ user_id: 3, is_active: false })
  })
})

describe('fetchSystemConfig', () => {
  it('should fetch config with auth header', async () => {
    const config = { registration_enabled: true, max_watchlist_items: 100 }
    mockOk(config)

    const result = await fetchSystemConfig(TOKEN)

    const [url, opts] = mockFetch.mock.calls[0]
    expect(url).toContain('/admin/system/config')
    expect(opts.headers.Authorization).toBe('Bearer test-token')
    expect(result).toEqual(config)
  })

  it('should throw on error', async () => {
    mockError(500, '服务器错误')

    await expect(fetchSystemConfig(TOKEN)).rejects.toThrow('服务器错误')
  })
})

describe('setRegistrationEnabled', () => {
  it('should POST with enabled=true query param', async () => {
    mockOk({ registration_enabled: true })

    const result = await setRegistrationEnabled(TOKEN, true)

    const [url, opts] = mockFetch.mock.calls[0]
    expect(url).toContain('/admin/system/config/registration?enabled=true')
    expect(opts.method).toBe('POST')
    expect(result).toEqual({ registration_enabled: true })
  })

  it('should POST with enabled=false query param', async () => {
    mockOk({ registration_enabled: false })

    await setRegistrationEnabled(TOKEN, false)

    const [url] = mockFetch.mock.calls[0]
    expect(url).toContain('enabled=false')
  })
})

describe('setMaxWatchlistItems', () => {
  it('should POST with max_items query param', async () => {
    mockOk({ max_watchlist_items: 200 })

    const result = await setMaxWatchlistItems(TOKEN, 200)

    const [url, opts] = mockFetch.mock.calls[0]
    expect(url).toContain('/admin/system/config/max-watchlist?max_items=200')
    expect(opts.method).toBe('POST')
    expect(result).toEqual({ max_watchlist_items: 200 })
  })
})
