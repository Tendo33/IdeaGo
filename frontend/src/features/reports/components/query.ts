const BROAD_QUERY_STOP_WORDS = new Set(['a', 'an', 'the', 'for', 'with', 'to', 'of', 'and', 'in'])

export function broadenQuery(query: string): string {
  const normalized = query.trim().replace(/\s+/g, ' ')
  if (!normalized) return query

  const candidates = [
    normalized
      .replace(/\b(niche|specialized|hyper-focused|targeted|exclusive)\b/gi, '')
      .replace(/\s+/g, ' ')
      .trim(),
    normalized.replace(/\s+\bfor\b\s+.+$/i, '').trim(),
    normalized
      .replace(/\bai\b/gi, 'software')
      .replace(/\bnotebook\b/gi, 'tool')
      .replace(/\s+/g, ' ')
      .trim(),
    `${normalized
      .split(' ')
      .map(token => token.toLowerCase())
      .filter(token => token.length > 2 && !BROAD_QUERY_STOP_WORDS.has(token))
      .slice(0, 4)
      .join(' ')} platform`.trim(),
  ]

  return candidates.find(candidate => candidate && candidate.toLowerCase() !== normalized.toLowerCase()) ?? `${normalized} market overview`
}
