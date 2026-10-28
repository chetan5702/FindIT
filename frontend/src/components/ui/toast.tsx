import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { CheckCircle2, CircleAlert, Info, X } from 'lucide-react'
import { cn } from '../../lib/cn'

type ToastKind = 'success' | 'error' | 'info'
interface ToastItem { id: number; title: string; description?: string; kind: ToastKind }
interface ToastContextValue { showToast: (toast: Omit<ToastItem, 'id'>) => void }
const ToastContext = createContext<ToastContextValue | null>(null)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const showToast = useCallback((toast: Omit<ToastItem, 'id'>) => {
    const id = Date.now() + Math.random()
    setToasts((items) => [...items, { ...toast, id }])
    window.setTimeout(() => setToasts((items) => items.filter((item) => item.id !== id)), 5000)
  }, [])
  const value = useMemo(() => ({ showToast }), [showToast])
  return <ToastContext.Provider value={value}>{children}<div className="fixed inset-x-4 bottom-20 z-[70] flex flex-col items-end gap-3 sm:bottom-5 sm:left-auto sm:w-96" aria-live="polite">{toasts.map((toast) => {
    const Icon = toast.kind === 'success' ? CheckCircle2 : toast.kind === 'error' ? CircleAlert : Info
    return <div key={toast.id} className={cn('flex w-full gap-3 rounded-2xl border bg-white p-4 shadow-lift animate-fade-up', toast.kind === 'error' ? 'border-red-200' : 'border-slate-200')} role={toast.kind === 'error' ? 'alert' : 'status'}><Icon className={cn('mt-0.5 h-5 w-5 shrink-0', toast.kind === 'success' ? 'text-emerald-600' : toast.kind === 'error' ? 'text-red-600' : 'text-blue-600')} /><div className="min-w-0 flex-1"><p className="text-sm font-bold text-slate-900">{toast.title}</p>{toast.description && <p className="mt-1 text-xs leading-5 text-slate-500">{toast.description}</p>}</div><button aria-label="Dismiss notification" className="self-start text-slate-400" onClick={() => setToasts((items) => items.filter((item) => item.id !== toast.id))}><X className="h-4 w-4" /></button></div>
  })}</div></ToastContext.Provider>
}

export function useToast() {
  const context = useContext(ToastContext)
  if (!context) throw new Error('useToast must be used inside ToastProvider')
  return context
}
