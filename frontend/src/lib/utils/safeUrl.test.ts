/**
 * These render sites receive URLs that an LLM extracted from third-party pages
 * (Reddit, GitHub, App Store, Tavily) or that a user typed into their profile.
 * They are untrusted input reaching `href` / `src`.
 */
import { describe, expect, it } from 'vitest'

import { safeHttpUrl, safeImageUrl, safeUrlHostname } from './safeUrl'

const SCRIPT_BEARING = [
  'javascript:alert(1)',
  'JavaScript:alert(1)',
  '  javascript:alert(1)  ',
  'jAvAsCrIpT:alert(1)',
  'vbscript:msgbox(1)',
  'data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==',
]

describe('safeHttpUrl', () => {
  it.each(['https://example.com/path?q=1', 'http://example.com'])(
    'allows plain http(s): %s',
    raw => {
      expect(safeHttpUrl(raw)).toBeTruthy()
    },
  )

  it.each(SCRIPT_BEARING)('rejects script-bearing scheme: %s', raw => {
    expect(safeHttpUrl(raw)).toBeNull()
  })

  it.each([
    ['empty', ''],
    ['whitespace', '   '],
    ['not a url', 'not a url'],
    ['scheme relative without base', '//example.com'],
    ['null', null],
    ['undefined', undefined],
  ])('rejects unusable input (%s)', (_label, raw) => {
    expect(safeHttpUrl(raw as string | null | undefined)).toBeNull()
  })

  it('rejects non-string input defensively', () => {
    expect(safeHttpUrl(42 as unknown as string)).toBeNull()
    expect(safeHttpUrl({} as unknown as string)).toBeNull()
  })

  it('rejects other non-web schemes', () => {
    expect(safeHttpUrl('file:///etc/passwd')).toBeNull()
    expect(safeHttpUrl('ftp://example.com')).toBeNull()
  })
})

describe('safeImageUrl', () => {
  it('allows http(s) and inline data images', () => {
    expect(safeImageUrl('https://cdn.example.com/a.png')).toBeTruthy()
    expect(safeImageUrl('data:image/png;base64,iVBORw0KGgo=')).toBeTruthy()
  })

  it('still rejects javascript: even though data: is allowed', () => {
    expect(safeImageUrl('javascript:alert(1)')).toBeNull()
    expect(safeImageUrl('vbscript:msgbox(1)')).toBeNull()
  })
})

describe('safeUrlHostname', () => {
  it('strips the www prefix', () => {
    expect(safeUrlHostname('https://www.example.com/x')).toBe('example.com')
  })

  it('returns null for unsafe or unparseable URLs', () => {
    expect(safeUrlHostname('javascript:alert(1)')).toBeNull()
    expect(safeUrlHostname('nonsense')).toBeNull()
  })
})
