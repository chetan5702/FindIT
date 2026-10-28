import { CalendarDays, MapPin, PackageOpen } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { Report } from '../types/api'
import { imageUrl } from '../lib/api'
import { formatDate } from '../lib/format'
import { Card } from './ui'
import { ReportTypeBadge, StatusBadge } from './ui/status'

export function ReportCard({ report, to }: { report: Report; to?: string }) {
  const image = report.images?.[0]
  return <Card className="group overflow-hidden transition duration-300 hover:-translate-y-1 hover:shadow-lift">
    <Link to={to ?? `/app/reports/${report.id}`} className="block rounded-2xl">
      <div className="relative aspect-[16/10] overflow-hidden bg-gradient-to-br from-pine-50 to-slate-100">{image ? <img className="h-full w-full object-cover transition duration-500 group-hover:scale-105" src={imageUrl(report.id, image)} alt={image.alt_text || report.item_name} loading="lazy" /> : <div className="grid h-full place-items-center text-slate-300"><PackageOpen className="h-12 w-12" /></div>}<div className="absolute left-3 top-3 flex gap-2"><ReportTypeBadge type={report.report_type} /><StatusBadge status={report.status} /></div></div>
      <div className="p-5"><p className="text-xs font-bold uppercase tracking-wider text-pine-700">{report.category?.name ?? 'Uncategorized'}</p><h3 className="mt-1.5 truncate text-lg font-bold transition group-hover:text-pine-700">{report.item_name}</h3><p className="mt-2 line-clamp-2 min-h-10 text-sm leading-5 text-slate-500">{report.description}</p><div className="mt-4 flex flex-col gap-2 border-t pt-4 text-xs text-slate-500"><span className="flex items-center gap-2 truncate"><MapPin className="h-3.5 w-3.5 shrink-0" />{report.location?.name ?? report.approximate_location ?? 'Location not specified'}</span><span className="flex items-center gap-2"><CalendarDays className="h-3.5 w-3.5" />{formatDate(report.occurred_at)}</span></div></div>
    </Link>
  </Card>
}
