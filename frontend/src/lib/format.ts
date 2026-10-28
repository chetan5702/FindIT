import { format, formatDistanceToNow, isValid, parseISO } from 'date-fns'

const parseDate = (value?: string | null) => value ? parseISO(value) : null

export function formatDate(value?: string | null, pattern = 'MMM d, yyyy') {
  const date = parseDate(value)
  return date && isValid(date) ? format(date, pattern) : 'Not provided'
}

export function formatDateTime(value?: string | null) {
  return formatDate(value, 'MMM d, yyyy · h:mm a')
}

export function timeAgo(value?: string | null) {
  const date = parseDate(value)
  return date && isValid(date) ? formatDistanceToNow(date, { addSuffix: true }) : 'Recently'
}

export function toDateTimeLocal(date = new Date()) {
  const offset = date.getTimezoneOffset() * 60_000
  return new Date(date.getTime() - offset).toISOString().slice(0, 16)
}
