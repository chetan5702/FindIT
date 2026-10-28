import { useState } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { Eye, EyeOff, LockKeyhole } from 'lucide-react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Button, Field, Input } from '../components/ui'
import { useToast } from '../components/ui/toast'
import { useAuth } from '../app/auth'
import { ApiError } from '../lib/api'

const loginSchema = z.object({ email: z.string().trim().email('Enter your campus email'), password: z.string().min(1, 'Enter your password') })
type LoginInput = z.infer<typeof loginSchema>

export function LoginPage() {
  const [showPassword, setShowPassword] = useState(false)
  const { login } = useAuth()
  const { showToast } = useToast()
  const navigate = useNavigate()
  const location = useLocation()
  const { register, handleSubmit, setError, formState: { errors, isSubmitting } } = useForm<LoginInput>({ resolver: zodResolver(loginSchema), defaultValues: { email: '', password: '' } })
  const submit = handleSubmit(async (values) => {
    try {
      const user = await login(values)
      showToast({ kind: 'success', title: `Welcome back, ${user.full_name.split(' ')[0]}` })
      const requested = (location.state as { from?: string } | null)?.from
      navigate(requested || (user.role === 'student' ? '/app' : user.role === 'staff' ? '/staff' : '/admin'), { replace: true })
    } catch (error) {
      const message = error instanceof ApiError ? error.message : 'Unable to sign in. Please try again.'
      setError('root', { message })
    }
  })
  return <div className="w-full"><p className="text-xs font-bold uppercase tracking-[.18em] text-pine-700">Welcome back</p><h1 className="mt-2 text-3xl font-extrabold">Sign in to FindIt</h1><p className="mt-2 text-sm leading-6 text-slate-500">Continue tracking your reports, matches, and claims.</p><form className="mt-8 space-y-5" onSubmit={submit} noValidate><Field label="Campus email" htmlFor="email" error={errors.email?.message} required><Input id="email" type="email" autoComplete="email" placeholder="you@suh.edu.in" aria-invalid={!!errors.email} {...register('email')} /></Field><Field label="Password" htmlFor="password" error={errors.password?.message} required><div className="relative"><Input id="password" type={showPassword ? 'text' : 'password'} autoComplete="current-password" className="pr-11" aria-invalid={!!errors.password} {...register('password')} /><button type="button" className="absolute right-1.5 top-1.5 rounded-lg p-2 text-slate-400 hover:bg-slate-100" onClick={() => setShowPassword(!showPassword)} aria-label={showPassword ? 'Hide password' : 'Show password'}>{showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</button></div></Field>{errors.root && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{errors.root.message}</div>}<Button className="w-full" size="lg" type="submit" loading={isSubmitting}>Sign in</Button></form><div className="mt-4 flex flex-wrap gap-4 text-sm"><Link to="/forgot-password" className="text-pine-700">Forgot password?</Link><Link to="/verify-email" className="text-pine-700">Verify institutional email</Link></div><p className="mt-6 text-center text-sm text-slate-500">New here? <Link className="font-bold text-pine-700 hover:text-pine-800" to="/register">Create a student account</Link></p><div className="mt-8 flex items-start gap-3 rounded-xl bg-slate-50 p-4"><LockKeyhole className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" /><p className="text-xs leading-5 text-slate-500">Staff and administrator accounts are provisioned securely by an administrator and cannot be self-registered.</p></div></div>
}

const registerSchema = z.object({
  full_name: z.string().trim().min(2, 'Enter your full name').max(120),
  email: z.string().trim().email('Enter a valid campus email'),
  password: z.string().min(12, 'Use at least 12 characters').regex(/[A-Z]/, 'Include an uppercase letter').regex(/[a-z]/, 'Include a lowercase letter').regex(/[0-9]/, 'Include a number'),
  confirm: z.string(),
  terms: z.literal(true, { errorMap: () => ({ message: 'Please accept the community guidelines' }) }),
}).refine((data) => data.password === data.confirm, { path: ['confirm'], message: 'Passwords do not match' })
type RegisterInput = z.infer<typeof registerSchema>

export function RegisterPage() {
  const { register: createAccount } = useAuth()
  const { showToast } = useToast()
  const navigate = useNavigate()
  const [showPassword, setShowPassword] = useState(false)
  const { register, handleSubmit, setError, watch, formState: { errors, isSubmitting } } = useForm<RegisterInput>({ resolver: zodResolver(registerSchema), defaultValues: { full_name: '', email: '', password: '', confirm: '', terms: false as true } })
  const [pendingMessage, setPendingMessage] = useState('')
  const password = watch('password')
  const submit = handleSubmit(async ({ full_name, email, password }) => {
    try { const result = await createAccount({ full_name, email, password }); if (result.verification_required) { setPendingMessage(result.message || 'Check your institutional inbox for a verification link.'); return } showToast({ kind: 'success', title: 'Your account is ready', description: 'Welcome to the campus recovery network.' }); navigate(result.user?.role === 'student' ? '/app' : '/', { replace: true }) }
    catch (error) { setError('root', { message: error instanceof Error ? error.message : 'Could not create your account.' }) }
  })
  if (pendingMessage) return <div><h1 className="text-2xl font-bold">Check your institutional email</h1><p role="status" className="mt-4">{pendingMessage}</p><Link to="/verify-email" className="mt-5 block text-pine-700">Request another verification email</Link><Link to="/login" className="mt-4 block">Return to sign in</Link></div>
  const strength = [password.length >= 12, /[A-Z]/.test(password), /[a-z]/.test(password), /[0-9]/.test(password)].filter(Boolean).length
  return <div className="w-full"><p className="text-xs font-bold uppercase tracking-[.18em] text-pine-700">Student access</p><h1 className="mt-2 text-3xl font-extrabold">Join your campus network</h1><p className="mt-2 text-sm leading-6 text-slate-500">Create an account to report items and receive private match updates.</p><form className="mt-7 space-y-4" onSubmit={submit} noValidate><Field label="Full name" htmlFor="full_name" error={errors.full_name?.message} required><Input id="full_name" autoComplete="name" placeholder="Your full name" {...register('full_name')} /></Field><Field label="Campus email" htmlFor="register-email" error={errors.email?.message} required><Input id="register-email" type="email" autoComplete="email" placeholder="you@suh.edu.in" {...register('email')} /></Field><Field label="Password" htmlFor="register-password" error={errors.password?.message} help="At least 12 characters with upper/lowercase and a number." required><div className="relative"><Input id="register-password" type={showPassword ? 'text' : 'password'} autoComplete="new-password" className="pr-11" {...register('password')} /><button type="button" aria-label={showPassword ? 'Hide password' : 'Show password'} className="absolute right-1.5 top-1.5 rounded-lg p-2 text-slate-400 hover:bg-slate-100" onClick={() => setShowPassword(!showPassword)}>{showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</button></div><div className="mt-2 grid grid-cols-4 gap-1" aria-label={`Password strength ${strength} out of 4`}>{[1,2,3,4].map((value) => <span key={value} className={`h-1 rounded-full ${value <= strength ? 'bg-pine-500' : 'bg-slate-200'}`} />)}</div></Field><Field label="Confirm password" htmlFor="confirm" error={errors.confirm?.message} required><Input id="confirm" type="password" autoComplete="new-password" {...register('confirm')} /></Field><label className="flex cursor-pointer items-start gap-3 rounded-xl border border-slate-200 p-3 text-xs leading-5 text-slate-600"><input type="checkbox" className="mt-0.5 h-4 w-4 rounded border-slate-300 text-pine-600 focus:ring-pine-500" {...register('terms')} /><span>I agree to use accurate information, respect privacy, and coordinate safe handovers through campus staff.</span></label>{errors.terms && <p className="field-error">{errors.terms.message}</p>}{errors.root && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{errors.root.message}</div>}<Button className="w-full" size="lg" type="submit" loading={isSubmitting}>Create account</Button></form><p className="mt-6 text-center text-sm text-slate-500">Already a member? <Link className="font-bold text-pine-700" to="/login">Sign in</Link></p></div>
}
