import { describe, it, expect } from 'vitest'
import { isAdmin, requireAdmin } from '@/lib/admin-guard'

describe('isAdmin', () => {
  it('should return true for admin user', () => {
    expect(isAdmin({ is_admin: true })).toBe(true)
  })

  it('should return false for non-admin user', () => {
    expect(isAdmin({ is_admin: false })).toBe(false)
  })

  it('should return false for null user', () => {
    expect(isAdmin(null)).toBe(false)
  })

  it('should return false for user without is_admin field', () => {
    expect(isAdmin({})).toBe(false)
  })
})

describe('requireAdmin', () => {
  it('should not throw for admin user', () => {
    expect(() => requireAdmin({ is_admin: true })).not.toThrow()
  })

  it('should throw for non-admin user', () => {
    expect(() => requireAdmin({ is_admin: false })).toThrow('Admin privileges required')
  })

  it('should throw for null user', () => {
    expect(() => requireAdmin(null)).toThrow('Authentication required')
  })
})
