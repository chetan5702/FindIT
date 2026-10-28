import { createContext, useContext, type ReactNode } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { authApi, type AuthResult } from '../lib/endpoints'
import { ApiError, resetCsrf } from '../lib/api'
import type { Role, User } from '../types/api'
import { PageSkeleton } from '../components/ui'
import { queryClient } from './query-client'

interface AuthContextValue {
  user: User | null
  isLoading: boolean
  login: (input: { email: string; password: string }) => Promise<User>
  register: (input: { full_name: string; email: string; password: string }) => Promise<AuthResult>
  logout: () => Promise<void>
  refresh: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const me = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: authApi.me,
    retry: false,
  })
  const loginMutation = useMutation({ mutationFn: authApi.login })
  const registerMutation = useMutation({ mutationFn: authApi.register })
  const logoutMutation = useMutation({ mutationFn: authApi.logout })
  const unauthenticated = me.error instanceof ApiError && me.error.status === 401

  const value: AuthContextValue = {
    user: unauthenticated ? null : me.data ?? null,
    isLoading: me.isLoading,
    login: async (input) => {
      const result = await loginMutation.mutateAsync(input)
      if (!result.user) throw new Error('Sign-in did not establish a session')
      // Authentication rotates the CSRF cookie; discard the token from the guest session.
      resetCsrf()
      await queryClient.cancelQueries()
      queryClient.clear()
      queryClient.setQueryData(['auth', 'me'], result.user)
      return result.user
    },
    register: async (input) => {
      const result = await registerMutation.mutateAsync(input)
      resetCsrf()
      await queryClient.cancelQueries()
      queryClient.clear()
      queryClient.setQueryData(['auth', 'me'], result.user)
      return result
    },
    logout: async () => {
      await logoutMutation.mutateAsync()
      resetCsrf()
      queryClient.clear()
      queryClient.setQueryData(['auth', 'me'], null)
    },
    refresh: async () => { await me.refetch() },
  }
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within AuthProvider')
  return context
}

export function ProtectedRoute({ roles }: { roles?: Role[] }) {
  const { user, isLoading } = useAuth()
  const location = useLocation()
  if (isLoading) return <div className="page-wrap py-12"><PageSkeleton /></div>
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  if (roles && !roles.includes(user.role)) return <Navigate to="/app" replace />
  return <Outlet />
}

export function GuestRoute() {
  const { user, isLoading } = useAuth()
  if (isLoading) return <div className="page-wrap py-12"><PageSkeleton cards={1} /></div>
  return user ? <Navigate to={user.role === 'student' ? '/app' : user.role === 'staff' ? '/staff' : '/admin'} replace /> : <Outlet />
}
