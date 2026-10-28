import { MapPinCheckInside } from 'lucide-react'
import { Link } from 'react-router-dom'
import { cn } from '../lib/cn'

export function Brand({ compact = false, dark = false, className }: { compact?: boolean; dark?: boolean; className?: string }) {
  return <Link to="/" className={cn('inline-flex items-center gap-2.5 rounded-lg', className)} aria-label="FindIt Next home">
    <span className={cn('grid h-9 w-9 place-items-center rounded-xl shadow-sm', dark ? 'bg-pine-300 text-ink-950' : 'bg-ink-900 text-white')}><MapPinCheckInside className="h-5 w-5" /></span>
    {!compact && <span className={cn('font-display text-lg font-extrabold tracking-tight', dark ? 'text-white' : 'text-ink-950')}>FindIt <span className={dark ? 'text-pine-300' : 'text-pine-600'}>Next</span></span>}
  </Link>
}
