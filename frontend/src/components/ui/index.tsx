import { createPortal } from 'react-dom'
import { useEffect, forwardRef, type ButtonHTMLAttributes, type HTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react'
import { AlertCircle, Inbox, LoaderCircle, X } from 'lucide-react'
import { cn } from '../../lib/cn'

type ButtonVariant = 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger'
interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> { variant?: ButtonVariant; size?: 'sm' | 'md' | 'lg'; loading?: boolean }
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button({ className, variant = 'primary', size = 'md', loading, children, disabled, ...props }, ref) {
  const variants: Record<ButtonVariant, string> = {
    primary: 'bg-ink-900 text-white hover:bg-ink-800 shadow-sm',
    secondary: 'bg-pine-100 text-pine-800 hover:bg-pine-200',
    outline: 'border border-slate-300 bg-white text-slate-700 hover:border-pine-400 hover:bg-pine-50',
    ghost: 'text-slate-600 hover:bg-slate-100 hover:text-ink-950',
    danger: 'bg-red-600 text-white hover:bg-red-700',
  }
  const sizes = { sm: 'h-9 px-3 text-sm rounded-lg', md: 'h-11 px-4 text-sm rounded-xl', lg: 'h-12 px-5 text-base rounded-xl' }
  return <button ref={ref} className={cn('inline-flex items-center justify-center gap-2 whitespace-nowrap font-semibold transition active:scale-[.98] disabled:pointer-events-none disabled:opacity-50', variants[variant], sizes[size], className)} disabled={disabled || loading} {...props}>
    {loading && <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden="true" />}{children}
  </button>
})

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) { return <div className={cn('surface', className)} {...props} /> }

type BadgeTone = 'neutral' | 'green' | 'blue' | 'amber' | 'red' | 'purple'
export function Badge({ children, tone = 'neutral', className }: { children: ReactNode; tone?: BadgeTone; className?: string }) {
  const tones = { neutral: 'bg-slate-100 text-slate-700', green: 'bg-emerald-100 text-emerald-800', blue: 'bg-blue-100 text-blue-800', amber: 'bg-amber-100 text-amber-800', red: 'bg-red-100 text-red-700', purple: 'bg-violet-100 text-violet-800' }
  return <span className={cn('inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold capitalize', tones[tone], className)}>{children}</span>
}

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input({ className, ...props }, ref) {
  return <input ref={ref} className={cn('h-11 w-full rounded-xl border border-slate-300 bg-white px-3.5 text-sm text-slate-900 shadow-sm transition placeholder:text-slate-400 hover:border-slate-400 focus:border-pine-500 focus:ring-2 focus:ring-pine-100 disabled:bg-slate-100', className)} {...props} />
})
export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(function Textarea({ className, ...props }, ref) {
  return <textarea ref={ref} className={cn('min-h-28 w-full resize-y rounded-xl border border-slate-300 bg-white px-3.5 py-3 text-sm text-slate-900 shadow-sm transition placeholder:text-slate-400 hover:border-slate-400 focus:border-pine-500 focus:ring-2 focus:ring-pine-100 disabled:bg-slate-100', className)} {...props} />
})
export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(function Select({ className, children, ...props }, ref) {
  return <select ref={ref} className={cn('h-11 w-full rounded-xl border border-slate-300 bg-white px-3.5 text-sm text-slate-900 shadow-sm transition hover:border-slate-400 focus:border-pine-500 focus:ring-2 focus:ring-pine-100', className)} {...props}>{children}</select>
})

export function Field({ label, htmlFor, error, help, required, children }: { label: string; htmlFor: string; error?: string; help?: string; required?: boolean; children: ReactNode }) {
  return <div>
    <label className="field-label" htmlFor={htmlFor}>{label}{required && <span className="ml-1 text-coral-500" aria-hidden="true">*</span>}</label>
    {children}
    {error ? <p id={`${htmlFor}-error`} role="alert" className="field-error">{error}</p> : help ? <p id={`${htmlFor}-help`} className="field-help">{help}</p> : null}
  </div>
}

export function Skeleton({ className }: { className?: string }) { return <div aria-hidden="true" className={cn('animate-soft-pulse rounded-xl bg-slate-200/80', className)} /> }
export function PageSkeleton({ cards = 3 }: { cards?: number }) { return <div className="space-y-6" aria-label="Loading"><Skeleton className="h-9 w-64" /><Skeleton className="h-5 w-96 max-w-full" /><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{Array.from({ length: cards }, (_, index) => <Skeleton key={index} className="h-52" />)}</div></div> }

export function EmptyState({ icon: Icon = Inbox, title, description, action }: { icon?: typeof Inbox; title: string; description: string; action?: ReactNode }) {
  return <div className="rounded-2xl border border-dashed border-slate-300 bg-white/60 px-6 py-14 text-center">
    <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-pine-50 text-pine-700"><Icon className="h-6 w-6" aria-hidden="true" /></span>
    <h3 className="mt-4 text-lg font-bold">{title}</h3><p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500">{description}</p>
    {action && <div className="mt-5">{action}</div>}
  </div>
}

export function ErrorState({ title = 'Something went wrong', error, retry }: { title?: string; error?: unknown; retry?: () => void }) {
  const message = error instanceof Error ? error.message : 'We could not load this information. Please try again.'
  return <div role="alert" className="rounded-2xl border border-red-200 bg-red-50 p-5 text-red-900">
    <div className="flex gap-3"><AlertCircle className="mt-0.5 h-5 w-5 shrink-0" /><div><p className="font-semibold">{title}</p><p className="mt-1 text-sm text-red-700">{message}</p>{retry && <Button className="mt-4" size="sm" variant="outline" onClick={retry}>Try again</Button>}</div></div>
  </div>
}

export function Modal({ open, onClose, title, description, children, footer }: { open: boolean; onClose: () => void; title: string; description?: string; children?: ReactNode; footer?: ReactNode }) {
  useEffect(() => {
    if (!open) return
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = previousOverflow }
  }, [open])
  if (!open) return null
  return createPortal(<div className="fixed inset-0 z-50 flex items-end justify-center overflow-x-hidden bg-ink-950/50 backdrop-blur-sm sm:items-center sm:p-4" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target) onClose() }}>
    <div role="dialog" aria-modal="true" aria-labelledby="modal-title" className="flex max-h-[92dvh] w-full min-w-0 max-w-lg flex-col overflow-hidden rounded-t-3xl bg-white shadow-lift sm:rounded-2xl">
      <div className="flex shrink-0 items-start justify-between gap-4 p-6"><div className="min-w-0 break-words"><h2 id="modal-title" className="text-xl font-bold">{title}</h2>{description && <p className="mt-1 text-sm leading-6 text-slate-500">{description}</p>}</div><button aria-label="Close dialog" className="shrink-0 rounded-lg p-2 text-slate-500 hover:bg-slate-100" onClick={onClose}><X className="h-5 w-5" /></button></div>
      {children && <div className="min-h-0 overflow-y-auto px-6 pb-1">{children}</div>}{footer && <div className="flex shrink-0 flex-col-reverse gap-2 p-6 sm:flex-row sm:justify-end">{footer}</div>}
    </div>
  </div>, document.body)
}

export function Pagination({ page, pages, onChange }: { page: number; pages: number; onChange: (page: number) => void }) {
  if (pages <= 1) return null
  return <nav className="mt-8 flex items-center justify-between" aria-label="Pagination"><Button variant="outline" size="sm" disabled={page <= 1} onClick={() => onChange(page - 1)}>Previous</Button><span className="text-sm text-slate-500">Page <strong className="text-slate-700">{page}</strong> of {pages}</span><Button variant="outline" size="sm" disabled={page >= pages} onClick={() => onChange(page + 1)}>Next</Button></nav>
}
