import { AccountSecurity } from '../components/account-security'
import { useState } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { Bell, BellOff, CheckCheck, ChevronRight, Mail, ShieldCheck, UserCircle } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useAuth } from '../app/auth'
import { queryClient } from '../app/query-client'
import { PageHeader } from '../components/page'
import { Button, Card, EmptyState, ErrorState, Field, Input, PageSkeleton, Pagination } from '../components/ui'
import { useToast } from '../components/ui/toast'
import { authApi, notificationsApi } from '../lib/endpoints'
import { timeAgo } from '../lib/format'
import { cn, initials } from '../lib/cn'

export function NotificationsPage() {
  const [page, setPage] = useState(1)
  const { showToast } = useToast()
  const notifications = useQuery({ queryKey: ['notifications', page], queryFn: () => notificationsApi.list(page), refetchInterval: 30_000 })
  const markRead = useMutation({ mutationFn: notificationsApi.read, onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications'] }) })
  const markAll = useMutation({ mutationFn: notificationsApi.readAll, onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ['notifications'] }); showToast({ kind: 'success', title: 'All caught up' }) } })
  const unread = notifications.data?.items.some((item) => !item.read_at)
  return <div className="mx-auto max-w-4xl"><PageHeader eyebrow="Your updates" title="Notifications" description="Match suggestions, claim decisions, and handover updates appear here." actions={unread && <Button variant="outline" loading={markAll.isPending} onClick={() => markAll.mutate()}><CheckCheck className="h-4 w-4" />Mark all read</Button>} />
    {notifications.isLoading ? <PageSkeleton cards={2} /> : notifications.isError ? <ErrorState error={notifications.error} retry={() => void notifications.refetch()} /> : notifications.data?.items.length ? <Card className="divide-y overflow-hidden">{notifications.data.items.map((item) => { const text = item.message ?? (item as { body?: string }).body ?? ''; const link = item.action_url ?? (item as { link?: string }).link; return <div key={item.id} className={cn('flex gap-4 p-5 transition', !item.read_at && 'bg-pine-50/60')}><span className={cn('grid h-10 w-10 shrink-0 place-items-center rounded-xl', item.read_at ? 'bg-slate-100 text-slate-500' : 'bg-pine-100 text-pine-700')}><Bell className="h-4 w-4" /></span><div className="min-w-0 flex-1"><div className="flex items-start justify-between gap-4"><div><p className="text-sm font-bold text-slate-900">{item.title}</p><p className="mt-1 text-sm leading-6 text-slate-600">{text}</p></div>{!item.read_at && <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-pine-500"><span className="sr-only">Unread</span></span>}</div><div className="mt-3 flex items-center justify-between"><p className="text-xs text-slate-400">{timeAgo(item.created_at)}</p><div className="flex items-center gap-3">{!item.read_at && <button className="text-xs font-bold text-pine-700" onClick={() => markRead.mutate(item.id)}>Mark read</button>}{link && <Link to={link} onClick={() => { if (!item.read_at) markRead.mutate(item.id) }} className="flex items-center text-xs font-bold text-slate-700">View <ChevronRight className="h-3.5 w-3.5" /></Link>}</div></div></div></div>})}</Card> : <EmptyState icon={BellOff} title="No notifications yet" description="WeÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ll let you know when a likely match appears or a claim moves forward." />}{notifications.data && <Pagination page={notifications.data.page} pages={notifications.data.pages} onChange={setPage} />}</div>
}

const profileSchema = z.object({ full_name: z.string().trim().min(2, 'Enter your full name').max(120) })
export function ProfilePage() {
  const { user, refresh } = useAuth()
  const { showToast } = useToast()
  const { register, handleSubmit, formState: { errors, isSubmitting, isDirty } } = useForm<{ full_name: string }>({ resolver: zodResolver(profileSchema), defaultValues: { full_name: user?.full_name ?? '' } })
  const submit = handleSubmit(async (values) => { try { await authApi.updateProfile(values); await refresh(); showToast({ kind: 'success', title: 'Profile updated' }) } catch (error) { showToast({ kind: 'error', title: 'Could not update profile', description: error instanceof Error ? error.message : undefined }) } })
  return <div className="mx-auto max-w-4xl"><PageHeader eyebrow="Account settings" title="Your profile" description="Manage the identity attached to your campus recovery activity." /><div className="grid gap-5 md:grid-cols-[15rem_1fr]"><Card className="p-6 text-center"><span className="mx-auto grid h-20 w-20 place-items-center rounded-3xl bg-pine-100 font-display text-2xl font-extrabold text-pine-800">{initials(user?.full_name ?? '')}</span><h2 className="mt-4 font-bold">{user?.full_name}</h2><p className="mt-1 truncate text-xs text-slate-500">{user?.email}</p><span className="mt-4 inline-flex rounded-full bg-slate-100 px-3 py-1 text-xs font-bold capitalize text-slate-600">{user?.role}</span></Card><div className="space-y-5"><AccountSecurity /><Card className="p-5 sm:p-7"><div className="flex items-center gap-3"><UserCircle className="h-5 w-5 text-pine-700" /><h2 className="text-lg font-bold">Personal details</h2></div><form className="mt-6 space-y-5" onSubmit={submit}><Field label="Full name" htmlFor="profile-name" error={errors.full_name?.message}><Input id="profile-name" autoComplete="name" {...register('full_name')} /></Field><Field label="Campus email" htmlFor="profile-email" help="Contact an administrator if your campus email needs to change."><Input id="profile-email" type="email" disabled value={user?.email ?? ''} /></Field><Button type="submit" loading={isSubmitting} disabled={!isDirty}>Save profile</Button></form></Card><Card className="p-5 sm:p-7"><div className="flex gap-3"><ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-pine-700" /><div><h2 className="font-bold">Privacy and safety</h2><p className="mt-2 text-sm leading-6 text-slate-500">Your email and ownership evidence are never included in public report responses. Staff access to sensitive claim data is permission-controlled and audited.</p></div></div></Card><Card className="p-5 sm:p-7"><div className="flex gap-3"><Mail className="mt-0.5 h-5 w-5 shrink-0 text-pine-700" /><div><h2 className="font-bold">In-app updates</h2><p className="mt-2 text-sm leading-6 text-slate-500">Notifications are checked periodically while FindIt is open. Verification and recovery emails are sent separately to your institutional inbox.</p></div></div></Card></div></div></div>
}
