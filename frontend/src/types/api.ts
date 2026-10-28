export type Role = 'student' | 'staff' | 'admin'
export type ReportType = 'lost' | 'found'
export type ReportStatus = 'open' | 'matched' | 'claimed' | 'returned' | 'archived' | 'removed'
export type ClaimStatus = 'submitted' | 'under_review' | 'approved' | 'rejected' | 'completed'

export interface User {
  id: string
  email: string
  full_name: string
  role: Role
  is_active: boolean
  email_verified: boolean
  created_at: string
}

export interface Category { id: string; name: string; description?: string | null; is_active?: boolean; created_at?: string }
export interface Location { id: string; name: string; description?: string | null; building?: string | null; is_active?: boolean; reporting_url?: string; created_at?: string }
export interface ReportImage { id: string; url?: string; content_type?: string; alt_text?: string | null; created_at?: string }

export interface Report {
  id: string
  report_type: ReportType
  item_name: string
  category_id: string
  category?: Category | null
  description: string
  approximate_location?: string | null
  location_id?: string | null
  location?: Location | null
  occurred_at: string
  public_details?: string | null
  private_details?: string | null
  status: ReportStatus
  owner_id?: string
  owner?: Pick<User, 'id' | 'full_name'>
  images: ReportImage[]
  can_edit?: boolean
  can_claim?: boolean
  created_at: string
  updated_at?: string
}

export interface MatchResult { report: Report; score: number; reasons: string[] }
export interface Evidence { id: string; file_name?: string; url?: string; content_type?: string; created_at?: string }
export interface Claim {
  id: string
  found_report_id: string
  found_report?: Report
  lost_report_id?: string | null
  lost_report?: Report | null
  claimant_id: string
  claimant?: User
  proof_text?: string
  status: ClaimStatus
  review_reason?: string | null
  evidence?: Evidence[]
  created_at: string
  updated_at?: string
  reviewed_at?: string | null
}

export interface CustodyRecord {
  id: string
  report_id: string
  report?: Report
  storage_location: string
  notes?: string | null
  received_at?: string
  released_at?: string | null
}

export interface Handover {
  id: string
  claim_id: string
  claim?: Claim
  claimant?: User
  staff_member?: User
  report?: Report
  notes?: string | null
  handed_over_at: string
}

export interface Notification {
  id: string
  title: string
  message: string
  kind?: 'match' | 'claim' | 'handover' | 'system'
  action_url?: string | null
  read_at?: string | null
  created_at: string
}

export interface AuditEvent {
  id: string
  action: string
  actor?: User | null
  actor_id?: string | null
  entity_type?: string
  entity_id?: string | null
  metadata?: Record<string, unknown> | null
  created_at: string
}

export interface Page<T> { items: T[]; total: number; page: number; page_size: number; pages: number }
export interface DashboardMetric { label: string; value: number; change?: number }
export interface StaffDashboardData { incoming_found?: number; in_custody?: number; pending_claims?: number; completed_returns?: number; recent_claims?: Claim[]; recent_found?: Report[] }
export interface AdminDashboardData { users?: number; active_reports?: number; staff?: number; returns?: number; categories?: number; locations?: number; reports_by_status?: Record<string, number> }
