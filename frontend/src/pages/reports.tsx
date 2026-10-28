import { useEffect, useMemo, useState, type ChangeEvent } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { CalendarDays, Camera, Filter, ImagePlus, MapPin, PackageOpen, Search, ShieldCheck, SlidersHorizontal, X } from 'lucide-react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { PageHeader } from '../components/page'
import { ReportCard } from '../components/report-card'
import { Button, Card, EmptyState, ErrorState, Field, Input, PageSkeleton, Pagination, Select, Textarea } from '../components/ui'
import { useToast } from '../components/ui/toast'
import { catalogApi, reportsApi } from '../lib/endpoints'
import { queryClient } from '../app/query-client'
import { toDateTimeLocal } from '../lib/format'
import type { ReportType } from '../types/api'

export function BrowseReportsPage({ publicMode = false }: { publicMode?: boolean }) {
  const [params, setParams] = useSearchParams()
  const page = Number(params.get('page') || '1')
  const q = params.get('q') ?? ''
  const type = params.get('report_type') ?? ''
  const categoryId = params.get('category_id') ?? ''
  const locationId = params.get('location_id') ?? ''
  const [search, setSearch] = useState(q)
  const [mobileFilters, setMobileFilters] = useState(false)
  const categories = useQuery({ queryKey: ['categories'], queryFn: catalogApi.categories })
  const locations = useQuery({ queryKey: ['locations'], queryFn: catalogApi.locations })
  const reports = useQuery({ queryKey: ['reports', { q, type, categoryId, locationId, page, publicMode }], queryFn: () => (publicMode ? reportsApi.publicList : reportsApi.list)({ q, report_type: type, category_id: categoryId, location_id: locationId, page, page_size: 12 }) })
  function update(key: string, value: string) { const next = new URLSearchParams(params); value ? next.set(key, value) : next.delete(key); next.delete('page'); setParams(next) }
  function submitSearch(event: React.FormEvent) { event.preventDefault(); update('q', search.trim()) }
  const filters = <div className="grid gap-3 md:grid-cols-3"><Select aria-label="Report type" value={type} onChange={(e) => update('report_type', e.target.value)}><option value="">Lost & found</option><option value="lost">Lost items</option><option value="found">Found items</option></Select><Select aria-label="Category" value={categoryId} onChange={(e) => update('category_id', e.target.value)}><option value="">All categories</option>{categories.data?.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select><Select aria-label="Location" value={locationId} onChange={(e) => update('location_id', e.target.value)}><option value="">All locations</option>{locations.data?.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></div>
  return <div className="mx-auto max-w-7xl"><PageHeader eyebrow="Campus listings" title="Browse reported items" description="Search public details only. Ownership evidence and distinctive private details are never shown here." actions={!publicMode && <><Link to="/app/report/lost"><Button variant="outline">Report lost</Button></Link><Link to="/app/report/found"><Button>Report found</Button></Link></>} />
    <Card className="mb-7 p-4"><form className="flex gap-2" onSubmit={submitSearch}><div className="relative flex-1"><Search className="absolute left-3.5 top-3.5 h-4 w-4 text-slate-400" /><Input aria-label="Search reports" className="pl-10" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search item name, description, or place" /></div><Button type="submit">Search</Button><Button type="button" variant="outline" className="px-3 md:hidden" onClick={() => setMobileFilters(!mobileFilters)} aria-label="Toggle filters"><SlidersHorizontal className="h-4 w-4" /></Button></form><div className={`${mobileFilters ? 'block' : 'hidden'} mt-3 md:block`}>{filters}</div>{(q || type || categoryId || locationId) && <div className="mt-3 flex items-center justify-between border-t pt-3"><p className="text-xs text-slate-500"><Filter className="mr-1 inline h-3.5 w-3.5" />Showing filtered results</p><button className="text-xs font-bold text-pine-700" onClick={() => { setSearch(''); setParams({}) }}>Clear all</button></div>}</Card>
    {reports.isLoading ? <PageSkeleton cards={6} /> : reports.isError ? <ErrorState error={reports.error} retry={() => void reports.refetch()} /> : reports.data?.items.length ? <><div className="mb-4 flex items-center justify-between"><p className="text-sm text-slate-500"><strong className="text-slate-800">{reports.data.total}</strong> {reports.data.total === 1 ? 'item' : 'items'} found</p><p className="text-xs text-slate-400">Newest reports first</p></div><div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">{reports.data.items.map((report) => <ReportCard key={report.id} report={report} to={publicMode ? '/login' : `/app/reports/${report.id}`} />)}</div><Pagination page={reports.data.page} pages={reports.data.pages} onChange={(nextPage) => { const next = new URLSearchParams(params); next.set('page', String(nextPage)); setParams(next); window.scrollTo({ top: 0, behavior: 'smooth' }) }} /></> : <EmptyState icon={PackageOpen} title="No items match those filters" description="Try a broader search, remove a filter, or create a report so the campus community can help." action={<Button variant="outline" onClick={() => { setSearch(''); setParams({}) }}>Reset filters</Button>} />}
  </div>
}

const reportSchema = z.object({
  item_name: z.string().trim().min(2, 'Name the item').max(120, 'Keep the name under 120 characters'),
  category_id: z.string().min(1, 'Choose a category'),
  description: z.string().trim().min(15, 'Add at least 15 characters').max(2000),
  location_id: z.string().optional(),
  approximate_location: z.string().trim().max(200).optional(),
  occurred_at: z.string().min(1, 'Choose the approximate date and time'),
  public_details: z.string().trim().max(1000).optional(),
  private_details: z.string().trim().max(2000).optional(),
}).refine((data) => !!data.location_id || !!data.approximate_location, { path: ['approximate_location'], message: 'Choose a campus location or describe the area' })
type ReportInput = z.infer<typeof reportSchema>
const allowedTypes = ['image/jpeg', 'image/png', 'image/webp']
const maxImageBytes = 5 * 1024 * 1024

export function ReportFormPage({ type: fixedType }: { type?: ReportType }) {
  const { id } = useParams()
  const editing = !!id
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const { showToast } = useToast()
  const categories = useQuery({ queryKey: ['categories'], queryFn: catalogApi.categories })
  const locations = useQuery({ queryKey: ['locations'], queryFn: catalogApi.locations })
  const existing = useQuery({ queryKey: ['report', id], queryFn: () => reportsApi.get(id!), enabled: editing })
  const type = fixedType ?? existing.data?.report_type ?? 'lost'
  const [files, setFiles] = useState<File[]>([])
  const [fileError, setFileError] = useState('')
  const previews = useMemo(() => files.map((file) => ({ file, url: URL.createObjectURL(file) })), [files])
  useEffect(() => () => previews.forEach((item) => URL.revokeObjectURL(item.url)), [previews])
  const { register, reset, handleSubmit, formState: { errors, isSubmitting } } = useForm<ReportInput>({ resolver: zodResolver(reportSchema), defaultValues: { item_name: '', category_id: '', description: '', location_id: params.get('location') ?? '', approximate_location: '', occurred_at: toDateTimeLocal(), public_details: '', private_details: '' } })
  useEffect(() => { if (existing.data) reset({ item_name: existing.data.item_name, category_id: existing.data.category_id, description: existing.data.description, location_id: existing.data.location_id ?? '', approximate_location: existing.data.approximate_location ?? '', occurred_at: toDateTimeLocal(new Date(existing.data.occurred_at)), public_details: existing.data.public_details ?? '', private_details: existing.data.private_details ?? '' }) }, [existing.data, reset])
  function chooseFiles(event: ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(event.target.files ?? [])
    if (files.length + selected.length > 5) { setFileError('You can upload up to 5 photos.'); return }
    const invalid = selected.find((file) => !allowedTypes.includes(file.type) || file.size > maxImageBytes)
    if (invalid) { setFileError('Use JPEG, PNG, or WebP images up to 5 MB each.'); return }
    setFiles((current) => [...current, ...selected]); setFileError(''); event.target.value = ''
  }
  const submit = handleSubmit(async (values) => {
    try {
      const payload = { ...values, report_type: type, occurred_at: new Date(values.occurred_at).toISOString(), location_id: values.location_id || null, approximate_location: values.approximate_location || null, public_details: values.public_details || null, private_details: values.private_details || null }
      const report = editing ? await reportsApi.update(id!, payload) : await reportsApi.create(payload)
      const failures: string[] = []
      for (const file of files) { try { await reportsApi.uploadImage(report.id, file) } catch { failures.push(file.name) } }
      await queryClient.invalidateQueries({ queryKey: ['reports'] })
      showToast({ kind: failures.length ? 'info' : 'success', title: editing ? 'Report updated' : `${type === 'lost' ? 'Lost' : 'Found'} item reported`, description: failures.length ? `${failures.length} photo upload${failures.length > 1 ? 's' : ''} did not finish. You can retry from the report.` : 'We’ll keep checking the campus network for likely matches.' })
      navigate(`/app/reports/${report.id}`, { replace: true })
    } catch (error) { showToast({ kind: 'error', title: 'Could not save report', description: error instanceof Error ? error.message : 'Please review the form and try again.' }) }
  })
  if (editing && existing.isLoading) return <PageSkeleton cards={1} />
  if (editing && existing.isError) return <ErrorState error={existing.error} retry={() => void existing.refetch()} />
  return <div className="mx-auto max-w-4xl"><PageHeader eyebrow={editing ? 'Update report' : type === 'lost' ? 'Start a search' : 'Help return an item'} title={editing ? `Edit ${existing.data?.item_name ?? 'report'}` : `Report a ${type} item`} description={editing ? 'Core identity fields may be locked once a claim exists to preserve the review history.' : type === 'lost' ? 'Share public clues that help matching, then add private ownership details only staff can review.' : 'Describe where and when you found it without publishing details that only the real owner would know.'} />
    <form onSubmit={submit} noValidate className="grid gap-6 lg:grid-cols-[1fr_19rem]"><div className="space-y-6"><Card className="p-5 sm:p-7"><SectionTitle number="01" title="Item details" /><div className="mt-6 grid gap-5 sm:grid-cols-2"><Field label="Item name" htmlFor="item_name" error={errors.item_name?.message} required><Input id="item_name" placeholder="e.g. Black wireless headphones" {...register('item_name')} /></Field><Field label="Category" htmlFor="category_id" error={errors.category_id?.message} required><Select id="category_id" {...register('category_id')}><option value="">Choose category</option>{categories.data?.filter((item) => item.is_active !== false).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></Field><div className="sm:col-span-2"><Field label="Description" htmlFor="description" error={errors.description?.message} help="Include color, material, brand, and general appearance. Keep unique proof private." required><Textarea id="description" rows={5} placeholder="Describe the item clearly…" {...register('description')} /></Field></div><div className="sm:col-span-2"><Field label="Additional public details" htmlFor="public_details" error={errors.public_details?.message} help="Optional context visible to signed-in campus members."><Textarea id="public_details" rows={3} placeholder="Case color, general condition, or non-sensitive context…" {...register('public_details')} /></Field></div></div></Card>
      <Card className="p-5 sm:p-7"><SectionTitle number="02" title="Place and time" /><div className="mt-6 grid gap-5 sm:grid-cols-2"><Field label="Campus location" htmlFor="location_id"><Select id="location_id" {...register('location_id')}><option value="">Choose a known location</option>{locations.data?.filter((item) => item.is_active !== false).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></Field><Field label="Approximate area" htmlFor="approximate_location" error={errors.approximate_location?.message} help="Useful if the exact campus location is not listed."><Input id="approximate_location" placeholder="e.g. second-floor study area" {...register('approximate_location')} /></Field><div className="sm:col-span-2"><Field label={`When it was ${type === 'lost' ? 'last seen' : 'found'}`} htmlFor="occurred_at" error={errors.occurred_at?.message} required><Input id="occurred_at" type="datetime-local" max={toDateTimeLocal()} {...register('occurred_at')} /></Field></div></div></Card>
      <Card className="p-5 sm:p-7"><SectionTitle number="03" title="Private verification" /><div className="mt-5 rounded-xl border border-pine-200 bg-pine-50 p-4"><div className="flex gap-3"><ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-pine-700" /><div><p className="text-sm font-bold text-pine-900">Visible only to you and authorized campus staff</p><p className="mt-1 text-xs leading-5 text-pine-800">Never add passwords, financial details, government IDs, or other unnecessary personal data.</p></div></div></div><div className="mt-5"><Field label={type === 'lost' ? 'Distinctive ownership details' : 'Details withheld for verification'} htmlFor="private_details" error={errors.private_details?.message} help={type === 'lost' ? 'Examples: a scratch, engraving, exact contents, serial suffix, or a unique sticker.' : 'Record a distinctive mark or detail the owner should be able to describe.'}><Textarea id="private_details" rows={4} placeholder="Private verification notes…" {...register('private_details')} /></Field></div></Card>
      {!editing && <Card className="p-5 sm:p-7"><SectionTitle number="04" title="Photos" /><p className="mt-2 text-sm text-slate-500">Add up to 5 clear photos. Avoid showing student IDs, addresses, or sensitive documents.</p><label className="mt-5 flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-slate-300 bg-slate-50 px-5 py-8 text-center transition hover:border-pine-400 hover:bg-pine-50"><ImagePlus className="h-7 w-7 text-pine-600" /><span className="mt-3 text-sm font-bold text-slate-700">Choose photos</span><span className="mt-1 text-xs text-slate-500">JPEG, PNG, or WebP · 5 MB each</span><input className="sr-only" type="file" multiple accept="image/jpeg,image/png,image/webp" onChange={chooseFiles} /></label>{fileError && <p role="alert" className="field-error">{fileError}</p>}{previews.length > 0 && <div className="mt-4 grid grid-cols-3 gap-3 sm:grid-cols-5">{previews.map(({ file, url }, index) => <div className="group relative aspect-square overflow-hidden rounded-xl border" key={`${file.name}-${index}`}><img src={url} alt={`Upload preview ${index + 1}`} className="h-full w-full object-cover" /><button type="button" className="absolute right-1 top-1 rounded-full bg-ink-950/80 p-1 text-white" onClick={() => setFiles((current) => current.filter((_, fileIndex) => fileIndex !== index))} aria-label={`Remove ${file.name}`}><X className="h-3.5 w-3.5" /></button></div>)}</div>}</Card>}
    </div><aside><div className="sticky top-24 space-y-4"><Card className="p-5"><h2 className="font-bold">Before you submit</h2><ul className="mt-4 space-y-3 text-xs leading-5 text-slate-600"><li className="flex gap-2"><Camera className="mt-0.5 h-4 w-4 shrink-0 text-pine-600" />Use a clear photo without sensitive information.</li><li className="flex gap-2"><MapPin className="mt-0.5 h-4 w-4 shrink-0 text-pine-600" />An approximate location is enough—do not guess.</li><li className="flex gap-2"><CalendarDays className="mt-0.5 h-4 w-4 shrink-0 text-pine-600" />A close date and time improves matching.</li></ul></Card><Button className="w-full" size="lg" type="submit" loading={isSubmitting}>{editing ? 'Save changes' : `Submit ${type} report`}</Button><Link to={editing ? `/app/reports/${id}` : '/app'} className="block"><Button className="w-full" type="button" variant="ghost">Cancel</Button></Link><p className="text-center text-[11px] leading-5 text-slate-400">Reports are reviewed under campus community guidelines.</p></div></aside></form>
  </div>
}

function SectionTitle({ number, title }: { number: string; title: string }) { return <div className="flex items-center gap-3"><span className="grid h-8 w-8 place-items-center rounded-lg bg-ink-900 text-xs font-bold text-white">{number}</span><h2 className="text-lg font-bold">{title}</h2></div> }
