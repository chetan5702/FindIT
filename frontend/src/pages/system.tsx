import { AlertTriangle, ArrowLeft, Home } from 'lucide-react'
import { isRouteErrorResponse, Link, Navigate, useRouteError } from 'react-router-dom'
import { useAuth } from '../app/auth'
import { Brand } from '../components/brand'
import { Button, Card } from '../components/ui'

export function RoleHomePage() {
  const { user } = useAuth()
  if (user?.role === 'staff') return <Navigate to="/staff" replace />
  if (user?.role === 'admin') return <Navigate to="/admin" replace />
  const StudentDashboard = lazyStudentDashboard
  return <StudentDashboard />
}

// Kept as a component indirection so role redirection happens before dashboard requests.
import { StudentDashboardPage as lazyStudentDashboard } from './student-dashboard'

export function NotFoundPage() {
  return <div className="grid min-h-screen place-items-center bg-cream-50 p-5"><Card className="w-full max-w-lg p-8 text-center sm:p-10"><Brand className="justify-center" /><p className="mt-8 font-display text-7xl font-extrabold text-pine-100">404</p><h1 className="mt-2 text-2xl font-extrabold">That page wandered off</h1><p className="mt-3 text-sm leading-6 text-slate-500">The link may be outdated, or you may not have access to this area.</p><div className="mt-7 flex justify-center gap-3"><Button variant="outline" onClick={() => history.back()}><ArrowLeft className="h-4 w-4" />Go back</Button><Link to="/"><Button><Home className="h-4 w-4" />Home</Button></Link></div></Card></div>
}

export function RouteErrorPage() {
  const error = useRouteError()
  const message = isRouteErrorResponse(error) ? error.statusText : error instanceof Error ? error.message : 'An unexpected error interrupted this page.'
  return <div className="grid min-h-screen place-items-center bg-cream-50 p-5"><Card className="w-full max-w-lg p-8 text-center"><span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-red-50 text-red-600"><AlertTriangle className="h-6 w-6" /></span><h1 className="mt-5 text-2xl font-extrabold">We hit a snag</h1><p className="mt-3 text-sm leading-6 text-slate-500">{message}</p><Button className="mt-6" onClick={() => window.location.reload()}>Reload page</Button></Card></div>
}
