function getAppLocale(language: string | undefined): string {
  const normalized = language?.toLowerCase().trim() ?? ''
  return normalized.startsWith('zh') ? 'zh-CN' : 'en-US'
}

export function formatAppDate(
  value: string | number | Date,
  language: string | undefined,
  options?: Intl.DateTimeFormatOptions,
): string {
  return new Date(value).toLocaleDateString(getAppLocale(language), options)
}

export function formatAppDateTime(
  value: string | number | Date,
  language: string | undefined,
  options?: Intl.DateTimeFormatOptions,
): string {
  return new Date(value).toLocaleString(getAppLocale(language), options)
}
