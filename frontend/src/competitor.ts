import type { Competitor } from './types/research'

export function getCompetitorId(competitor: Pick<Competitor, 'name' | 'source_urls' | 'links'>): string {
  const primarySourceUrl = competitor.source_urls.find(url => Boolean(url))
  if (primarySourceUrl) return `source:${primarySourceUrl}`

  const primaryLink = competitor.links.find(link => Boolean(link))
  if (primaryLink) return `link:${primaryLink}`

  return `name:${competitor.name.trim().toLowerCase()}`
}

function hashId(value: string): string {
  let hash = 0
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0
  }
  return hash.toString(36)
}

export function getCompetitorDomIdFromId(competitorId: string): string {
  const slug = competitorId
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 36) || 'item'
  return `competitor-${slug}-${hashId(competitorId)}`
}

export function getCompetitorDomId(competitor: Pick<Competitor, 'name' | 'source_urls' | 'links'>): string {
  return getCompetitorDomIdFromId(getCompetitorId(competitor))
}
