import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { authApi } from '../lib/endpoints'
import { Button, Field, Input } from '../components/ui'

export function IdentityPage({ mode }: { mode: 'verify' | 'forgot' | 'reset' }) {
  const [token] = useState(() => new URLSearchParams(window.location.hash.slice(1)).get('token') ?? '')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)
  // Tokens stay in memory, not browser history, query strings or referrers.
  useEffect(() => { if (window.location.hash) window.history.replaceState(null, '', window.location.pathname) }, [])
  const title = mode === 'verify' ? 'Verify institutional email' : mode === 'forgot' ? 'Recover your account' : 'Set a new password'
  async function submit(event: FormEvent) {
    event.preventDefault(); setError(''); setBusy(true)
    try {
      if ((mode === 'reset' || (mode === 'verify' && token)) && password !== confirm) throw new Error('Passwords do not match')
      if (mode === 'reset' && !token) throw new Error('Open the complete recovery link from your email')
      const result = mode === 'reset' ? await authApi.resetPassword(token, password)
        : mode === 'verify' && token ? await authApi.verifyEmail(token, password)
        : mode === 'verify' ? await authApi.requestVerification(email) : await authApi.forgotPassword(email)
      setMessage(result.message); setDone(true)
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Please try again') }
    finally { setBusy(false) }
  }
  return <div><h1 className="text-2xl font-bold">{title}</h1><p className="mt-3 text-sm text-slate-600">Use your institutional account. Choose your own password when verifying. Links expire and can only be used once.</p>
    {!done && <form className="mt-6 space-y-5" onSubmit={submit}>
      {(mode === 'forgot' || (mode === 'verify' && !token)) && <Field label="Institutional email" htmlFor="identity-email"><Input id="identity-email" type="email" required value={email} onChange={e => setEmail(e.target.value)} placeholder="you@suh.edu.in" /></Field>}
      {(mode === 'reset' || (mode === 'verify' && token)) && <><Field label="New password" htmlFor="new-password" help="At least 12 characters with a letter and a number."><Input id="new-password" type="password" autoComplete="new-password" minLength={12} maxLength={128} required value={password} onChange={e => setPassword(e.target.value)} /></Field><Field label="Confirm new password" htmlFor="confirm-password"><Input id="confirm-password" type="password" autoComplete="new-password" required value={confirm} onChange={e => setConfirm(e.target.value)} /></Field></>}
      <Button type="submit" loading={busy}>{mode === 'reset' ? 'Reset password' : mode === 'verify' && token ? 'Confirm email verification' : 'Send email'}</Button>
    </form>}
    {message && <p role="status" className="mt-5 text-pine-800">{message}</p>}{error && <p role="alert" className="mt-5 text-red-700">{error}</p>}
    <Link to="/login" className="mt-6 block text-sm text-pine-700">Return to sign in</Link>
  </div>
}
