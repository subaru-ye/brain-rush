import Taro from "@tarojs/taro"

import { loginWithWechat } from "@/services/api"
import type { AuthSession } from "@/types/learning"

const AUTH_SESSION_KEY = "brain-rush-auth-session"

export function getAuthSession(): AuthSession | null {
  try {
    const session = Taro.getStorageSync<AuthSession>(AUTH_SESSION_KEY)
    return session || null
  } catch {
    return null
  }
}

export function saveAuthSession(session: AuthSession): void {
  Taro.setStorageSync(AUTH_SESSION_KEY, session)
}

export function clearAuthSession(): void {
  Taro.removeStorageSync(AUTH_SESSION_KEY)
}

export async function ensureAuthSession(): Promise<AuthSession> {
  const cached = getAuthSession()
  if (cached?.token) {
    return cached
  }

  const loginResult = await Taro.login()
  if (!loginResult.code) {
    throw new Error("微信登录失败，请稍后重试")
  }

  const session = await loginWithWechat(loginResult.code)
  saveAuthSession(session)
  return session
}
