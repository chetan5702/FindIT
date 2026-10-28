import { Badge } from './index'
import type { ClaimStatus, ReportStatus } from '../../types/api'

export function StatusBadge({ status }: { status: ClaimStatus | ReportStatus | string }) {
  const tone = status === 'completed' || status === 'returned' || status === 'approved' ? 'green'
    : status === 'rejected' || status === 'removed' ? 'red'
      : status === 'under_review' || status === 'claimed' ? 'amber'
        : status === 'matched' ? 'purple' : 'blue'
  return <Badge tone={tone}>{status.replaceAll('_', ' ')}</Badge>
}

export function ReportTypeBadge({ type }: { type: 'lost' | 'found' }) {
  return <Badge tone={type === 'lost' ? 'amber' : 'green'}>{type}</Badge>
}
