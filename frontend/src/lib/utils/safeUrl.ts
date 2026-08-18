/**
 * URL safety for third-party content.
 *
 * Competitor links, evidence URLs and avatar URLs all originate outside our
 * trust boundary: the pipeline extracts them, via an LLM, from Reddit posts,
 * GitHub READMEs, App Store listings and Tavily crawls. Rendering an untrusted
 * string straight into `href` or `src` invites `javascript:` and `data:` URLs.
 *
 * The strict CSP already blocks `javascript:` execution, so this is
 * defence-in-depth rather than the only barrier — but the CSP is one config
 * change away from being relaxed, and `data:` documents are not covered by it
 * at all.
 */

const SAFE_LINK_PROTOCOLS = new Set(['http:', 'https:'])
const SAFE_IMAGE_PROTOCOLS = new Set(['http:', 'https:', 'data:'])

function parse(raw: string): URL | null {
  const candidate = raw.trim()
  if (!candidate) return null
  try {
    return new URL(candidate)
  } catch {
    return null
  }
}

/**
 * Return the URL when it is safe to put in an `href`, otherwise `null`.
 * Callers render `null` as plain text rather than a link.
 */
export function safeHttpUrl(raw: string | null | undefined): string | null {
  if (typeof raw !== 'string') return null
  const parsed = parse(raw)
  if (!parsed) return null
  return SAFE_LINK_PROTOCOLS.has(parsed.protocol) ? parsed.href : null
}

/**
 * Return the URL when it is safe to put in an `<img src>`, otherwise `null`.
 * Allows `data:` because avatars are sometimes inlined, but still refuses
 * `javascript:` and other script-bearing schemes.
 */
export function safeImageUrl(raw: string | null | undefined): string | null {
  if (typeof raw !== 'string') return null
  const parsed = parse(raw)
  if (!parsed) return null
  return SAFE_IMAGE_PROTOCOLS.has(parsed.protocol) ? parsed.href : null
}

/** Display host for a URL, or `null` when the URL is unusable. */
export function safeUrlHostname(raw: string | null | undefined): string | null {
  const safe = safeHttpUrl(raw)
  if (!safe) return null
  try {
    return new URL(safe).hostname.replace(/^www\./, '')
  } catch {
    return null
  }
}
