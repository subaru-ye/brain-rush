const ADMIN_TOKEN_KEY = "brain-rush-admin-token"

export function getStoredAdminToken(): string {
  return window.localStorage.getItem(ADMIN_TOKEN_KEY) || ""
}

export function saveAdminToken(token: string): void {
  window.localStorage.setItem(ADMIN_TOKEN_KEY, token)
}

export function clearAdminToken(): void {
  window.localStorage.removeItem(ADMIN_TOKEN_KEY)
}
