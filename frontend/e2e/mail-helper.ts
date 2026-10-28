import { expect } from '@playwright/test'
import { readdir, readFile } from 'node:fs/promises'
import path from 'node:path'

// Only the explicitly configured private test mail sink is inspected.
export async function readIdentityToken(email: string, purpose: string) {
  const directory = process.env.FINDIT_MAIL_DIRECTORY
  if (!directory) throw new Error('FINDIT_MAIL_DIRECTORY must point to a private test mail sink')
  let token = ''
  await expect.poll(async () => {
    for (const file of (await readdir(directory).catch(() => [])).sort().reverse()) {
      if (!file.endsWith('.eml')) continue
      const message = (await readFile(path.join(directory, file), 'utf8')).replace(/=\r?\n/g, '').replace(/=([0-9a-f]{2})/gi, (_match, hex: string) => String.fromCharCode(parseInt(hex, 16)))
      if (!message.includes(`To: ${email}`) || !message.includes(`/${purpose}#token=`)) continue
      token = message.match(/#token=([A-Za-z0-9_-]+)/)?.[1] ?? ''
      if (token) return true
    }
    return false
  }, { timeout: 10_000, message: 'Expected an identity email in the private test sink' }).toBe(true)
  return token
}
