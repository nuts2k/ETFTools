interface User {
  is_admin?: boolean
}

export function isAdmin(user: User | null): boolean {
  return user?.is_admin === true
}

export function requireAdmin(user: User | null): void {
  if (!user) {
    throw new Error('Authentication required')
  }
  if (!user.is_admin) {
    throw new Error('Admin privileges required')
  }
}
