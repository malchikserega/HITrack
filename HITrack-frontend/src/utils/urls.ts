export const safeExternalUrl = (value?: string | null): string | undefined => {
  if (!value) return undefined
  try {
    const url = new URL(value)
    return url.protocol === 'https:' || url.protocol === 'http:' ? url.toString() : undefined
  } catch {
    return undefined
  }
}

export const openSafeExternalUrl = (value?: string | null): void => {
  const url = safeExternalUrl(value)
  if (url) window.open(url, '_blank', 'noopener,noreferrer')
}
