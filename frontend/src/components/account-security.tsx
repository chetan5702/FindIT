import { useState, type FormEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { authApi } from '../lib/endpoints'
import { queryClient } from '../app/query-client'
import { Button, Card, Field, Input } from './ui'

export function AccountSecurity() {
  const sessions = useQuery({ queryKey: ['auth-sessions'], queryFn: authApi.sessions })
  const [current, setCurrent] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  function signedOut() { queryClient.clear(); window.location.assign('/login') }
  async function change(event: FormEvent) {
    event.preventDefault(); setMessage(''); setBusy(true)
    try {
      if (password !== confirm) throw new Error('Passwords do not match')
      await authApi.changePassword(current, password); signedOut()
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Please try again') }
    finally { setBusy(false) }
  }
  async function revoke(id: string, current: boolean) {
    try { await authApi.revokeSession(id); if (current) signedOut(); else await sessions.refetch() }
    catch (error) { setMessage(error instanceof Error ? error.message : 'Could not revoke session') }
  }
  return <><Card className="p-5 sm:p-7"><h2 className="text-lg font-bold">Password and access</h2><form className="mt-5 space-y-4" onSubmit={change}>
    <Field label="Current password" htmlFor="current-password"><Input id="current-password" type="password" autoComplete="current-password" required maxLength={128} value={current} onChange={e => setCurrent(e.target.value)} /></Field>
    <Field label="New password" htmlFor="profile-password" help="At least 12 characters with a letter and a number."><Input id="profile-password" type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={password} onChange={e => setPassword(e.target.value)} /></Field>
    <Field label="Confirm password" htmlFor="profile-confirm"><Input id="profile-confirm" type="password" autoComplete="new-password" required value={confirm} onChange={e => setConfirm(e.target.value)} /></Field>
    <Button type="submit" loading={busy}>Change password and sign out</Button></form>{message && <p role="alert" className="mt-4 text-red-700">{message}</p>}</Card>
    <Card className="p-5 sm:p-7"><h2 className="text-lg font-bold">Active sessions</h2>{sessions.isError && <p role="alert">Could not load sessions.</p>}<ul className="mt-4 divide-y">{sessions.data?.map(session => <li key={session.id} className="flex flex-wrap items-center justify-between gap-3 py-3"><span className="min-w-0 text-sm">{session.current ? 'This device' : session.user_agent || 'Another device'}<span className="block text-xs text-slate-500">Expires {new Date(session.expires_at).toLocaleString()}</span></span><Button variant="outline" size="sm" onClick={() => void revoke(session.id, session.current)}>Sign out session</Button></li>)}</ul><Button variant="outline" onClick={async () => { try { await authApi.logoutAll(); signedOut() } catch { setMessage('Could not sign out all sessions') } }}>Sign out all devices</Button></Card></>
}
