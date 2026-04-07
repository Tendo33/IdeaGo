interface ClientMetricPayload {
  name: string
  detail: Record<string, string | number | boolean | null>
  timestamp: string
}

declare global {
  interface Window {
    __IDEAGO_CLIENT_METRICS__?: ClientMetricPayload[]
  }
}

const CLIENT_METRIC_EVENT = 'ideago:metric'

function normalizeDetail(detail: Record<string, unknown>): Record<string, string | number | boolean | null> {
  const normalized: Record<string, string | number | boolean | null> = {}
  for (const [key, value] of Object.entries(detail)) {
    if (
      typeof value === 'string' ||
      typeof value === 'number' ||
      typeof value === 'boolean' ||
      value === null
    ) {
      normalized[key] = value
      continue
    }
    normalized[key] = value == null ? null : String(value)
  }
  return normalized
}

export function recordClientMetric(name: string, detail: Record<string, unknown> = {}): void {
  if (typeof window === 'undefined') return

  const payload: ClientMetricPayload = {
    name,
    detail: normalizeDetail(detail),
    timestamp: new Date().toISOString(),
  }

  if (!window.__IDEAGO_CLIENT_METRICS__) {
    window.__IDEAGO_CLIENT_METRICS__ = []
  }
  window.__IDEAGO_CLIENT_METRICS__.push(payload)
  window.dispatchEvent(new CustomEvent(CLIENT_METRIC_EVENT, { detail: payload }))
}
