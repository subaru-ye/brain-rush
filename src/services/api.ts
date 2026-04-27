import Taro from "@tarojs/taro"

import type {
  GenerateQuizResponse,
  GenerateReportResponse,
  QuizQuestion,
  UserAnswer
} from "@/types/learning"

function getErrorMessage(data: unknown): string {
  if (data && typeof data === "object" && "detail" in data) {
    const detail = (data as { detail?: unknown }).detail
    if (typeof detail === "string") {
      return detail
    }
  }
  return "服务暂时开小差了，请稍后重试"
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
    throw new Error(getErrorMessage(response.data))
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
