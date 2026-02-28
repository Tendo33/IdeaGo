import type { Competitor } from './types/research'

export function getCompetitorId(competitor: Pick<Competitor, 'name' | 'source_urls' | 'links'>): string {
  const primarySourceUrl = competitor.source_urls.find(url => Boolean(url))
  if (primarySourceUrl) return `source:${primarySourceUrl}`

  const primaryLink = competitor.links.find(link => Boolean(link))
  if (primaryLink) return `link:${primaryLink}`

  return `name:${competitor.name.trim().toLowerCase()}`
}
