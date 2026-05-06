import type { QuizQuestion, UserAnswer } from "@/types/learning"

const optionLabels = ["A", "B", "C", "D"]

export function getQuestionType(question: QuizQuestion) {
  return question.questionType || (
    getAnswerIndexes(question).length > 1 ? "multiple_choice" : "single_choice"
  )
}

export function getAnswerIndexes(question: QuizQuestion): number[] {
  const indexes = question.answerIndexes?.length
    ? question.answerIndexes
    : question.answerIndex !== undefined
      ? [question.answerIndex]
      : []
  return Array.from(new Set(indexes)).sort((a, b) => a - b)
}

export function getSelectedIndexes(answer: UserAnswer): number[] {
  const indexes = answer.selectedIndexes?.length
    ? answer.selectedIndexes
    : answer.selectedIndex !== undefined
      ? [answer.selectedIndex]
      : []
  return Array.from(new Set(indexes)).sort((a, b) => a - b)
}

export function isAnswerCorrectByIndexes(
  question: QuizQuestion,
  selectedIndexes: number[]
): boolean {
  const answerIndexes = getAnswerIndexes(question)
  const normalizedSelected = Array.from(new Set(selectedIndexes)).sort((a, b) => a - b)
  return (
    answerIndexes.length === normalizedSelected.length &&
    answerIndexes.every((value, index) => value === normalizedSelected[index])
  )
}

export function isAnswerCorrect(question: QuizQuestion, answer: UserAnswer): boolean {
  return isAnswerCorrectByIndexes(question, getSelectedIndexes(answer))
}

export function createUserAnswer(
  question: QuizQuestion,
  selectedIndexes: number[],
  startedAt: number,
  answeredAt = Date.now()
): UserAnswer {
  const normalizedSelected = Array.from(new Set(selectedIndexes)).sort((a, b) => a - b)
  return {
    questionId: question.id,
    selectedIndex: normalizedSelected[0],
    selectedIndexes: normalizedSelected,
    isCorrect: isAnswerCorrectByIndexes(question, normalizedSelected),
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
    return question ? isAnswerCorrect(question, answer) : false
  }).length
}

export function getAccuracyPercent(
  questions: QuizQuestion[],
  answers: UserAnswer[]
): number {
  if (!questions.length) return 0
  return Math.round((getCorrectCount(questions, answers) / questions.length) * 100)
}

export function formatAnswerText(question: QuizQuestion, indexes: number[]): string {
  return indexes
    .filter((index) => index >= 0 && index < question.options.length)
    .map((index) => `${optionLabels[index]}，${question.options[index]}`)
    .join("；")
}
