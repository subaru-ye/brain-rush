import { getWrongQuestions } from "@/services/api"
import { ensureAuthSession } from "@/services/auth"
import { saveCurrentSession } from "@/services/session"
import type { QuizQuestion, QuizSession, WrongQuestionItem } from "@/types/learning"

export async function loadWrongQuestions(): Promise<WrongQuestionItem[]> {
  const auth = await ensureAuthSession()
  const response = await getWrongQuestions(auth.token)
  return response.items
}

export function createWrongReviewSession(items: WrongQuestionItem[]): QuizSession {
  const questions: QuizQuestion[] = items.map((item) => ({
    id: `${item.recordId}_${item.questionId}`,
    stem: item.stem,
    options: item.options,
    answerIndex: item.answerIndex,
    explanation: item.explanation,
    knowledgePoint: item.knowledgePoint
  }))

  return {
    sessionId: `wrong-review-${Date.now()}`,
    topic: "错题复训",
    questions,
    answers: [],
    mode: "wrong_review"
  }
}

export function startWrongQuestionReview(items: WrongQuestionItem[]): QuizSession {
  const session = createWrongReviewSession(items)
  saveCurrentSession(session)
  return session
}
