import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import { IdentityPage } from '../pages/identity'
import { authApi } from '../lib/endpoints'

afterEach(() => window.history.replaceState(null, '', '/'))

it('keeps verification tokens out of history and requires explicit password confirmation', async () => {
  const token = 'test-token-with-at-least-thirty-two-characters'
  window.history.replaceState(null, '', `/verify-email#token=${token}`)
  const verify = vi.spyOn(authApi, 'verifyEmail').mockResolvedValue({ message: 'Email verified. You can now sign in.' })
  render(<MemoryRouter><IdentityPage mode="verify" /></MemoryRouter>)
  expect(window.location.hash).toBe('')
  expect(verify).not.toHaveBeenCalled()
  fireEvent.change(screen.getByLabelText('New password'), { target: { value: 'ChosenPassword123!' } })
  fireEvent.change(screen.getByLabelText('Confirm new password'), { target: { value: 'ChosenPassword123!' } })
  fireEvent.click(screen.getByRole('button', { name: 'Confirm email verification' }))
  await waitFor(() => expect(verify).toHaveBeenCalledWith(token, 'ChosenPassword123!'))
  expect(await screen.findByRole('status')).toHaveTextContent('Email verified')
})

it('does not submit a recovery password when confirmation differs', async () => {
  window.history.replaceState(null, '', '/reset-password#token=token-for-recovery-test-123456789012345')
  const reset = vi.spyOn(authApi, 'resetPassword')
  render(<MemoryRouter><IdentityPage mode="reset" /></MemoryRouter>)
  fireEvent.change(screen.getByLabelText('New password'), { target: { value: 'ChosenPassword123!' } })
  fireEvent.change(screen.getByLabelText('Confirm new password'), { target: { value: 'DifferentPassword123!' } })
  fireEvent.click(screen.getByRole('button', { name: 'Reset password' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Passwords do not match')
  expect(reset).not.toHaveBeenCalled()
})

it('shows the generic recovery message without revealing account existence', async () => {
  const request = vi.spyOn(authApi, 'forgotPassword').mockResolvedValue({ message: 'If the account is eligible, an email will arrive with the next steps.' })
  render(<MemoryRouter><IdentityPage mode="forgot" /></MemoryRouter>)
  fireEvent.change(screen.getByLabelText('Institutional email'), { target: { value: 'student@suh.edu.in' } })
  fireEvent.click(screen.getByRole('button', { name: 'Send email' }))
  expect(await screen.findByRole('status')).toHaveTextContent('If the account is eligible')
  expect(request).toHaveBeenCalledWith('student@suh.edu.in')
})
