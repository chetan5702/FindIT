import { useState, type ReactNode } from 'react'
import { Bell, Boxes, ChartNoAxesCombined, ChevronDown, ClipboardCheck, FileSearch, Handshake, History, Home, LayoutDashboard, LogOut, MapPinned, Menu, PlusCircle, Search, Settings, ShieldCheck, Tags, UserCircle, Users, X } from 'lucide-react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Brand } from './brand'
import { Button } from './ui'
import { useAuth } from '../app/auth'
import { notificationsApi } from '../lib/endpoints'
import { cn, initials } from '../lib/cn'

export function PublicLayout() {
  const { user } = useAuth()
  return <div className="min-h-screen bg-cream-50"><header className="sticky top-0 z-40 border-b border-white/70 bg-cream-50/90 backdrop-blur-xl"><div className="page-wrap flex h-16 items-center justify-between"><Brand /><nav className="hidden items-center gap-7 text-sm font-semibold text-slate-600 md:flex" aria-label="Main navigation"><Link className="hover:text-pine-700" to="/browse">Browse items</Link><Link className="hover:text-pine-700" to="/#how-it-works">How it works</Link><Link className="hover:text-pine-700" to="/#safety">Safe returns</Link></nav><div className="flex items-center gap-2">{user ? <Link to={user.role === 'student' ? '/app' : user.role === 'staff' ? '/staff' : '/admin'}><Button size="sm">Open dashboard</Button></Link> : <><Link className="hidden text-sm font-semibold text-slate-600 hover:text-ink-950 sm:inline" to="/login">Sign in</Link><Link to="/register"><Button size="sm">Join campus</Button></Link></>}</div></div></header><main id="main-content"><Outlet /></main><Footer /></div>
}

function Footer() { return <footer className="border-t border-slate-200 bg-white"><div className="page-wrap flex flex-col gap-5 py-8 sm:flex-row sm:items-center sm:justify-between"><Brand /><p className="text-sm text-slate-500">A safer way to reunite campus belongings with their people.</p><div className="flex gap-5 text-sm text-slate-500"><Link to="/browse">Browse</Link><Link to="/login">Sign in</Link></div></div></footer> }

interface NavItem { label: string; to: string; icon: typeof Home; end?: boolean }
const studentNav: NavItem[] = [
  { label: 'Overview', to: '/app', icon: Home, end: true }, { label: 'Browse items', to: '/app/browse', icon: Search }, { label: 'My activity', to: '/app/activity', icon: FileSearch }, { label: 'Notifications', to: '/app/notifications', icon: Bell }, { label: 'Profile', to: '/app/profile', icon: UserCircle },
]
const staffNav: NavItem[] = [
  { label: 'Staff overview', to: '/staff', icon: LayoutDashboard, end: true }, { label: 'Custody', to: '/staff/custody', icon: Boxes }, { label: 'Verify claims', to: '/staff/claims', icon: ClipboardCheck }, { label: 'Handovers', to: '/staff/handovers', icon: Handshake }, { label: 'Browse reports', to: '/app/browse', icon: Search },
]
const adminNav: NavItem[] = [
  { label: 'Admin overview', to: '/admin', icon: ChartNoAxesCombined, end: true }, { label: 'Categories', to: '/admin/categories', icon: Tags }, { label: 'Campus locations', to: '/admin/locations', icon: MapPinned }, { label: 'Users & staff', to: '/admin/users', icon: Users }, { label: 'Audit history', to: '/admin/audit', icon: History }, { label: 'Staff operations', to: '/staff', icon: ShieldCheck },
]

export function AppLayout({ kind }: { kind: 'student' | 'staff' | 'admin' }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)
  const notifications = useQuery({ queryKey: ['notifications', 1], queryFn: () => notificationsApi.list(1), refetchInterval: 60_000, enabled: !!user })
  const unread = notifications.data?.items.filter((item) => !item.read_at).length ?? 0
  const items = kind === 'student' ? studentNav : kind === 'staff' ? staffNav : adminNav
  const home = kind === 'student' ? '/app' : `/${kind}`
  const title = kind === 'student' ? 'Student space' : kind === 'staff' ? 'Staff workspace' : 'Administration'
  async function handleLogout() { await logout(); navigate('/') }
  return <div className="min-h-screen bg-slate-50">
    <aside className={cn('fixed inset-y-0 left-0 z-50 w-72 bg-ink-950 p-4 text-white transition-transform lg:translate-x-0', mobileOpen ? 'translate-x-0' : '-translate-x-full')}>
      <div className="flex h-12 items-center justify-between px-2"><Brand dark /><button className="rounded-lg p-2 text-slate-300 hover:bg-white/10 lg:hidden" onClick={() => setMobileOpen(false)} aria-label="Close menu"><X className="h-5 w-5" /></button></div>
      <div className="mt-8 px-3"><p className="text-[11px] font-bold uppercase tracking-[.18em] text-pine-300/80">{title}</p></div>
      <nav className="mt-3 space-y-1" aria-label={`${kind} navigation`}>{items.map((item) => <NavLink key={item.to} to={item.to} end={item.end} onClick={() => setMobileOpen(false)} className={({ isActive }) => cn('flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold transition', isActive ? 'bg-white text-ink-950 shadow-sm' : 'text-slate-300 hover:bg-white/10 hover:text-white')}><item.icon className="h-[18px] w-[18px]" aria-hidden="true" />{item.label}</NavLink>)}</nav>
      <div className="absolute inset-x-4 bottom-5 rounded-2xl bg-white/[.07] p-3"><div className="flex items-center gap-3"><span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-pine-300 font-bold text-ink-950">{initials(user?.full_name ?? '')}</span><div className="min-w-0"><p className="truncate text-sm font-semibold">{user?.full_name}</p><p className="truncate text-xs text-slate-400">{user?.email}</p></div></div></div>
    </aside>
    {mobileOpen && <button className="fixed inset-0 z-40 bg-ink-950/40 lg:hidden" aria-label="Close menu overlay" onClick={() => setMobileOpen(false)} />}
    <div className="lg:pl-72"><header className="sticky top-0 z-30 border-b border-slate-200/80 bg-white/90 backdrop-blur-xl"><div className="flex h-16 items-center justify-between px-4 sm:px-6 lg:px-8"><div className="flex items-center gap-3"><button className="rounded-xl p-2 text-slate-600 hover:bg-slate-100 lg:hidden" onClick={() => setMobileOpen(true)} aria-label="Open menu"><Menu className="h-5 w-5" /></button><Link to={home} className="font-display text-sm font-bold text-ink-950 lg:hidden">FindIt Next</Link><span className="hidden text-sm text-slate-500 lg:block">Campus Recovery Network</span></div><div className="flex items-center gap-2">{kind === 'student' && <Link to="/app/report/lost" className="hidden sm:block"><Button size="sm"><PlusCircle className="h-4 w-4" />New report</Button></Link>}<Link to={kind === 'student' ? '/app/notifications' : '/app/notifications'} className="relative rounded-xl p-2.5 text-slate-600 hover:bg-slate-100" aria-label={`${unread} unread notifications`}><Bell className="h-5 w-5" />{unread > 0 && <span className="absolute right-1 top-1 grid min-h-4 min-w-4 place-items-center rounded-full bg-coral-500 px-1 text-[9px] font-bold text-white">{unread > 9 ? '9+' : unread}</span>}</Link><div className="relative"><button className="flex items-center gap-2 rounded-xl p-1.5 hover:bg-slate-100" onClick={() => setProfileOpen(!profileOpen)} aria-expanded={profileOpen}><span className="grid h-8 w-8 place-items-center rounded-lg bg-pine-100 text-xs font-bold text-pine-800">{initials(user?.full_name ?? '')}</span><ChevronDown className="hidden h-4 w-4 text-slate-400 sm:block" /></button>{profileOpen && <div className="absolute right-0 mt-2 w-56 rounded-xl border bg-white p-2 shadow-lift"><div className="px-3 py-2"><p className="truncate text-sm font-semibold text-slate-900">{user?.full_name}</p><p className="truncate text-xs text-slate-500">{user?.email}</p></div><Link to="/app/profile" className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-50" onClick={() => setProfileOpen(false)}><Settings className="h-4 w-4" />Profile settings</Link><button className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-red-600 hover:bg-red-50" onClick={handleLogout}><LogOut className="h-4 w-4" />Sign out</button></div>}</div></div></div></header>
      <main id="main-content" className="px-4 py-7 pb-24 sm:px-6 lg:px-8 lg:py-9"><Outlet /></main>
    </div>
    {kind === 'student' && <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t border-slate-200 bg-white px-1 pb-[env(safe-area-inset-bottom)] shadow-[0_-4px_20px_rgba(15,23,42,.06)] lg:hidden" aria-label="Mobile navigation">{studentNav.map((item) => <NavLink key={item.to} to={item.to} end={item.end} className={({ isActive }) => cn('flex flex-col items-center gap-1 px-1 py-2 text-[10px] font-semibold', isActive ? 'text-pine-700' : 'text-slate-500')}><item.icon className="h-5 w-5" />{item.label.replace(' items', '')}</NavLink>)}</nav>}
  </div>
}

export function DynamicAppLayout() {
  const { user } = useAuth()
  return <AppLayout kind={user?.role === 'admin' ? 'admin' : user?.role === 'staff' ? 'staff' : 'student'} />
}

export function AuthLayout({ children }: { children?: ReactNode }) { return <div className="grid min-h-screen bg-white lg:grid-cols-[1fr_1.05fr]"><div className="flex min-h-screen flex-col p-5 sm:p-8 lg:p-12"><Brand /><div className="mx-auto flex w-full max-w-md flex-1 items-center py-10">{children ?? <Outlet />}</div><p className="text-xs text-slate-400">Protected by secure, campus-only recovery workflows.</p></div><div className="relative hidden overflow-hidden bg-ink-950 lg:block"><div className="absolute -right-32 -top-24 h-96 w-96 rounded-full bg-pine-400/20 blur-3xl" /><div className="absolute -bottom-40 -left-28 h-[28rem] w-[28rem] rounded-full bg-coral-400/15 blur-3xl" /><div className="relative flex h-full flex-col justify-between p-14 text-white"><p className="text-xs font-bold uppercase tracking-[.2em] text-pine-300">Campus community, connected</p><blockquote className="max-w-xl"><p className="font-display text-4xl font-bold leading-tight">“The best lost-and-found feels less like a noticeboard and more like a trusted handoff.”</p><footer className="mt-6 text-sm text-slate-300">Private evidence. Staff verification. Safer returns.</footer></blockquote><div className="grid grid-cols-3 gap-3">{['Explainable matching', 'Verified ownership', 'Audited handovers'].map((text) => <div key={text} className="rounded-2xl border border-white/10 bg-white/[.06] p-4 text-sm font-semibold text-slate-200">{text}</div>)}</div></div></div></div> }
