import type { ReactNode } from 'react'
import { ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'

export function PageHeader({ eyebrow, title, description, actions, children }: { eyebrow?: string; title: string; description?: string; actions?: ReactNode; children?: ReactNode }) {
  return <header className="mb-7 flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
    <div className="min-w-0">{eyebrow && <p className="mb-2 text-xs font-bold uppercase tracking-[.18em] text-pine-700">{eyebrow}</p>}<h1 className="text-2xl font-extrabold tracking-tight sm:text-3xl">{title}</h1>{description && <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500 sm:text-base">{description}</p>}{children}</div>
    {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
  </header>
}

export function Breadcrumbs({ items }: { items: { label: string; to?: string }[] }) {
  return <nav aria-label="Breadcrumb" className="mb-5 flex items-center gap-1 overflow-hidden text-sm text-slate-500">{items.map((item, index) => <span key={`${item.label}-${index}`} className="flex min-w-0 items-center gap-1">{index > 0 && <ChevronRight className="h-4 w-4 shrink-0 text-slate-300" />}{item.to ? <Link className="truncate rounded hover:text-pine-700" to={item.to}>{item.label}</Link> : <span className="truncate font-medium text-slate-700" aria-current="page">{item.label}</span>}</span>)}</nav>
}
