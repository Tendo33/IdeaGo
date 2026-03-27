const RETRYABLE_HTTP_STATUS = new Set([408, 409, 425, 429, 500, 502, 503, 504])

export function findLastSseBoundary(buffer: string): number {
  const boundaryPattern = /\r?\n\r?\n/g
  let boundaryEnd = -1
  let match: RegExpExecArray | null
  while ((match = boundaryPattern.exec(buffer)) !== null) {
    boundaryEnd = match.index + match[0].length
  }
  return boundaryEnd
}

export function shouldRetrySseStatus(statusCode: number): boolean {
  if (statusCode >= 200 && statusCode < 300) {
    return false
  }
  if (statusCode >= 400 && statusCode < 500) {
    return RETRYABLE_HTTP_STATUS.has(statusCode)
  }
  return true
}

/**
 * Parse a single SSE chunk buffer into individual events.
 * Returns emitted { eventType, data } pairs.
 */
export function* parseSseChunk(buffer: string): Generator<{ eventType: string; data: string }> {
  const blocks = buffer.split(/\r?\n\r?\n/)
  for (const block of blocks) {
    if (!block.trim()) continue
    let eventType = 'message'
    const dataLines: string[] = []
    for (const line of block.split(/\r?\n/)) {
      if (line.startsWith('event:')) {
        eventType = line.slice(6).trim()
      } else if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trimStart())
      }
    }
    const data = dataLines.join('\n')
    if (data) yield { eventType, data }
  }
}
