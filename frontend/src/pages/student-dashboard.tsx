import { useQuery } from '@tanstack/react-query'
import { ArrowRight, Bell, CheckCircle2, ClipboardList, Plus, Search, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useAuth } from '../app/auth'
import { PageHeader } from '../components/page'
import { ReportCard } from '../components/report-card'
import { Button, Card, EmptyState, ErrorState, PageSkeleton } from '../components/ui'
import { claimsApi, notificationsApi, reportsApi } from '../lib/endpoints'

export function StudentDashboardPage() {
  const { user } = useAuth()
  const reports = useQuery({ queryKey: ['reports', 'mine', 1], queryFn: () => reportsApi.list({ mine: true, page: 1, page_size: 4 }) })
  const claims = useQuery({ queryKey: ['claims', 'mine', 1], queryFn: () => claimsApi.list({ page: 1, page_size: 5 }) })
  const notifications = useQuery({ queryKey: ['notifications', 1], queryFn: () => notificationsApi.list(1) })
  if (reports.isLoading && claims.isLoading) return <PageSkeleton />
  const reportItems = reports.data?.items ?? []
  const claimItems = claims.data?.items ?? []
  const unread = notifications.data?.items.filter((item) => !item.read_at).length ?? 0
  const openReports = reportItems.filter((item) => !['returned', 'archived', 'removed'].includes(item.status)).length
  const pendingClaims = claimItems.filter((item) => ['submitted', 'under_review', 'approved'].includes(item.status)).length
  return <div className="mx-auto max-w-7xl"><PageHeader eyebrow="Student dashboard" title={`Good to see you, ${user?.full_name.split(' ')[0] ?? 'there'}`} description="Keep an eye on your reports, review suggested matches, and follow claim updates." actions={<><Link to="/app/report/found"><Button variant="outline"><Plus className="h-4 w-4" />Found an item</Button></Link><Link to="/app/report/lost"><Button><Plus className="h-4 w-4" />Report lost</Button></Link></>} />
    {(reports.isError || claims.isError) && <ErrorState error={reports.error ?? claims.error} retry={() => { void reports.refetch(); void claims.refetch() }} />}
    <div className="grid gap-4 sm:grid-cols-3">{[
      { icon: ClipboardList, label: 'Open reports', value: openReports, tone: 'bg-blue-50 text-blue-700' }, { icon: Sparkles, label: 'Active claims', value: pendingClaims, tone: 'bg-violet-50 text-violet-700' }, { icon: Bell, label: 'Unread updates', value: unread, tone: 'bg-amber-50 text-amber-700' },
    ].map(({ icon: Icon, label, value, tone }) => <Card className="flex items-center gap-4 p-5" key={label}><span className={`grid h-11 w-11 place-items-center rounded-2xl ${tone}`}><Icon className="h-5 w-5" /></span><div><p className="font-display text-2xl font-extrabold text-ink-950">{value}</p><p className="text-sm text-slate-500">{label}</p></div></Card>)}</div>
    <section className="mt-8"><div className="mb-4 flex items-center justify-between"><div><h2 className="text-xl font-bold">Your recent reports</h2><p className="mt-1 text-sm text-slate-500">The latest items you have shared with campus.</p></div><Link to="/app/activity" className="flex items-center gap-1 text-sm font-bold text-pine-700">View all <ArrowRight className="h-4 w-4" /></Link></div>{reportItems.length ? <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{reportItems.map((report) => <ReportCard key={report.id} report={report} />)}</div> : <EmptyState icon={Search} title="No reports yet" description="Lost or found something? Creating a detailed report gives the matching system a place to start." action={<Link to="/app/report/lost"><Button>Create your first report</Button></Link>} />}</section>
    <section className="mt-8 grid gap-4 lg:grid-cols-[1.35fr_.65fr]"><Card className="p-5 sm:p-6"><div className="flex items-center justify-between"><div><h2 className="text-xl font-bold">Claim activity</h2><p className="mt-1 text-sm text-slate-500">Ownership reviews stay private between you and campus staff.</p></div><Link to="/app/activity?tab=claims" className="text-sm font-bold text-pine-700">View all</Link></div>{claimItems.length ? <div className="mt-5 divide-y">{claimItems.slice(0, 3).map((claim) => <Link to={`/app/claims/${claim.id}`} key={claim.id} className="flex items-center gap-3 py-3 first:pt-0 last:pb-0"><span className="grid h-9 w-9 place-items-center rounded-xl bg-pine-50 text-pine-700"><CheckCircle2 className="h-4 w-4" /></span><div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold">{claim.found_report?.item_name ?? 'Ownership claim'}</p><p className="text-xs capitalize text-slate-500">{claim.status.replaceAll('_', ' ')}</p></div><ArrowRight className="h-4 w-4 text-slate-300" /></Link>)}</div> : <p className="mt-5 text-sm text-slate-500">No claims submitted yet.</p>}</Card><Card className="overflow-hidden bg-ink-950 p-6 text-white"><Sparkles className="h-6 w-6 text-pine-300" /><h2 className="mt-5 text-xl font-bold text-white">Search the campus network</h2><p className="mt-2 text-sm leading-6 text-slate-300">Browse recently found items and filter by place, category, or date.</p><Link to="/app/browse" className="mt-5 inline-block"><Button className="bg-pine-300 text-ink-950 hover:bg-pine-200">Browse items <ArrowRight className="h-4 w-4" /></Button></Link></Card></section>
  </div>
}
