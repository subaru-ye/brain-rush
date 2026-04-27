import Taro from "@tarojs/taro"

import type { QuizSession } from "@/types/learning"

const CURRENT_SESSION_KEY = "brain-rush-current-session"

export function saveCurrentSession(session: QuizSession): void {
  Taro.setStorageSync(CURRENT_SESSION_KEY, session)
}

export function getCurrentSession(): QuizSession | null {
  try {
    const session = Taro.getStorageSync<QuizSession>(CURRENT_SESSION_KEY)
    return session || null
  } catch {
    return null
  }
}

export function clearCurrentSession(): void {
  Taro.removeStorageSync(CURRENT_SESSION_KEY)
}
