import type { QuizQuestion, UserAnswer } from "@/types/learning"

export function isAnswerCorrect(question: QuizQuestion, selectedIndex: number): boolean {
  return selectedIndex === question.answerIndex
}

export function createUserAnswer(
  question: QuizQuestion,
  selectedIndex: number,
  startedAt: number,
  answeredAt = Date.now()
): UserAnswer {
  return {
    questionId: question.id,
    selectedIndex,
    isCorrect: isAnswerCorrect(question, selectedIndex),
    elapsedMs: answeredAt - startedAt
  }
}

export function findFirstUnansweredIndex(
  questions: QuizQuestion[],
  answers: UserAnswer[]
): number {
  return questions.findIndex(
    (question) => !answers.some((answer) => answer.questionId === question.id)
  )
}

export function getCorrectCount(
  questions: QuizQuestion[],
  answers: UserAnswer[]
): number {
  const questionById = new Map(questions.map((question) => [question.id, question]))
  return answers.filter((answer) => {
    const question = questionById.get(answer.questionId)
    return question ? isAnswerCorrect(question, answer.selectedIndex) : false
  }).length
}

export function getAccuracyPercent(
  questions: QuizQuestion[],
  answers: UserAnswer[]
): number {
  if (!questions.length) return 0
  return Math.round((getCorrectCount(questions, answers) / questions.length) * 100)
}
