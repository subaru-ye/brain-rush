import Taro from "@tarojs/taro"

import type {
  GenerateQuizResponse,
  GenerateReportResponse,
  QuizQuestion,
  UserAnswer
} from "@/types/learning"

export type AppErrorCode =
  | "ai_timeout"
  | "ai_rate_limited"
  | "ai_auth_error"
  | "ai_invalid_response"
  | "ai_connection_error"
  | "ai_upstream_error"
  | string

export class AppError extends Error {
  code: AppErrorCode
  detail: string
  statusCode: number

  constructor(code: AppErrorCode, detail: string, statusCode: number) {
    super(detail)
    this.name = "AppError"
    this.code = code
    this.detail = detail
    this.statusCode = statusCode
  }
}

export function isAppError(error: unknown): error is AppError {
  return error instanceof AppError
}

function getErrorDetail(data: unknown): string {
  if (data && typeof data === "object" && "detail" in data) {
    const detail = (data as { detail?: unknown }).detail
    if (typeof detail === "string") {
      return detail
    }
  }
  return "服务暂时开小差了，请稍后重试"
}

function getErrorCode(data: unknown): AppErrorCode {
  if (data && typeof data === "object" && "code" in data) {
    const code = (data as { code?: unknown }).code
    if (typeof code === "string") {
      return code
    }
  }
  return "unknown_error"
}

export function getFriendlyErrorMessage(error: unknown, fallback: string): string {
  if (!isAppError(error)) {
    return error instanceof Error ? error.message : fallback
  }

  const messageByCode: Partial<Record<AppErrorCode, string>> = {
    ai_timeout: "AI 生成超时了，请稍后重试",
    ai_rate_limited: "当前生成请求较多，请稍后再试",
    ai_auth_error: "AI 服务配置暂不可用，请检查后端配置",
    ai_invalid_response: "AI 返回结果格式异常，请重新生成",
    ai_connection_error: "暂时连不上 AI 服务，请检查网络后重试",
    ai_upstream_error: "AI 服务暂时不可用，请稍后重试"
  }

  return messageByCode[error.code] || error.detail || fallback
}

async function postJson<TResponse>(path: string, data: unknown): Promise<TResponse> {
  const response = await Taro.request<TResponse>({
    url: `${API_BASE_URL}${path}`,
    method: "POST",
    data,
    header: {
      "content-type": "application/json"
    }
  })

  if (response.statusCode < 200 || response.statusCode >= 300) {
    throw new AppError(
      getErrorCode(response.data),
      getErrorDetail(response.data),
      response.statusCode
    )
  }

  return response.data
}

export function generateQuiz(inputText: string): Promise<GenerateQuizResponse> {
  return postJson<GenerateQuizResponse>("/api/generate-quiz", { inputText })
}

export function generateReport(
  topic: string,
  questions: QuizQuestion[],
  answers: UserAnswer[]
): Promise<GenerateReportResponse> {
  return postJson<GenerateReportResponse>("/api/generate-report", {
    topic,
    questions,
    answers
  })
}
