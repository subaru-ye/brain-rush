import Taro from "@tarojs/taro"

import { createProductEvent } from "@/services/api"
import { getAuthSession } from "@/services/auth"

const CLIENT_ID_KEY = "brain-rush-client-id"

export interface TrackEventPayload {
  page: string
  sessionId?: string
  topic?: string
  properties?: Record<string, unknown>
}

function createClientId(): string {
  return `client-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

export function getOrCreateClientId(): string {
  try {
    const cached = Taro.getStorageSync<string>(CLIENT_ID_KEY)
    if (cached) {
      return cached
    }
    const nextId = createClientId()
    Taro.setStorageSync(CLIENT_ID_KEY, nextId)
    return nextId
  } catch {
    return createClientId()
  }
}

export async function trackEvent(eventName: string, payload: TrackEventPayload): Promise<void> {
  try {
    const auth = getAuthSession()
    await createProductEvent(
      {
        eventName,
        clientId: getOrCreateClientId(),
        page: payload.page,
        sessionId: payload.sessionId,
        topic: payload.topic,
        properties: payload.properties || {},
        occurredAt: new Date().toISOString()
      },
      auth?.token
    )
  } catch {
    // 埋点失败不能影响学习主流程。
  }
}
