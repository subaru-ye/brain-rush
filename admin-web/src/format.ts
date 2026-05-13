export function formatDate(value?: string | null): string {
  if (!value) {
    return "-"
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  })
}

export function parseTags(value: string): string[] {
  return value
    .split(/[\n,，]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

export function tagsText(tags: string[]): string {
  return tags.join(", ")
}

export function activeLabel(isActive: boolean): string {
  return isActive ? "Active" : "Inactive"
}

export function embeddingLabel(embeddedAt?: string | null): string {
  return embeddedAt ? "Embedded" : "Missing"
}
