import { createQuestionFeedback } from "@/services/api"
import { ensureAuthSession } from "@/services/auth"
import type { QuestionFeedbackRequest, QuestionFeedbackResponse } from "@/types/learning"

export async function submitQuestionFeedback(
  payload: QuestionFeedbackRequest
): Promise<QuestionFeedbackResponse> {
  const auth = await ensureAuthSession()
  return createQuestionFeedback(payload, auth.token)
}
