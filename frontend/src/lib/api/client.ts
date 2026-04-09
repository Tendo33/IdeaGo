export {
  ApiError,
  API_BASE,
  DEFAULT_TIMEOUT_MS,
  ANALYSIS_TIMEOUT_MS,
  authHeaders,
  mutationHeaders,
  isApiError,
  isRequestAbortError,
  fetchWithTimeout,
  buildErrorMessage,
  throwApiError,
  type ListReportsOptions,
  type RequestOptions,
} from './core'

export {
  startAnalysis,
  getReport,
  getReportWithStatus,
  getReportRuntimeStatus,
  listReports,
  deleteReport,
  cancelAnalysis,
  exportReport,
  getStreamUrl,
  type ReportFetchResult,
} from './reportsClient'

export {
  refreshAuthToken,
  startLinuxDoAuth,
  getMe,
  logoutAuthSession,
  getQuotaInfo,
  getMyProfile,
  updateMyProfile,
  deleteAccount,
  type CurrentUser,
  type DeleteAccountResult,
  type QuotaInfo,
  type StartLinuxDoAuthOptions,
  type UserProfile,
} from './authClient'

export {
  adminGetStats,
  adminListUsers,
  adminSetQuota,
  type AdminStats,
  type AdminUser,
} from './adminClient'

import {
  API_BASE,
  DEFAULT_TIMEOUT_MS,
  type RequestOptions,
} from './core'

// --- Billing ---

export interface SubscriptionStatus {
  plan: string
  has_subscription: boolean
  stripe_configured: boolean
}

export async function getSubscriptionStatus(options: RequestOptions = {}): Promise<SubscriptionStatus> {
  void options
  throw new Error('Billing is temporarily disabled')
}

export async function createCheckoutSession(
  successUrl: string,
  cancelUrl: string,
  options: RequestOptions = {},
): Promise<string> {
  void API_BASE
  void DEFAULT_TIMEOUT_MS
  void successUrl
  void cancelUrl
  void options
  throw new Error('Billing is temporarily disabled')
}

export async function createPortalSession(
  returnUrl: string,
  options: RequestOptions = {},
): Promise<string> {
  void API_BASE
  void DEFAULT_TIMEOUT_MS
  void returnUrl
  void options
  throw new Error('Billing is temporarily disabled')
}
