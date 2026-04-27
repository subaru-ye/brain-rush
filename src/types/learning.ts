export interface QuizQuestion {
  id: string
  stem: string
  options: string[]
  answerIndex: number
  explanation: string
  knowledgePoint: string
}

export interface GenerateQuizResponse {
  sessionId: string
  topic: string
  questions: QuizQuestion[]
}

export interface UserAnswer {
  questionId: string
  selectedIndex: number
  isCorrect: boolean
  elapsedMs?: number
}

export interface WrongQuestionReview {
  questionId: string
  stem: string
  userAnswer: string
  correctAnswer: string
  explanation: string
  knowledgePoint: string
}

export interface ReviewReport {
  score: number
  accuracy: number
  summary: string
  weakPoints: string[]
  wrongQuestions: WrongQuestionReview[]
  suggestions: string[]
}

export interface GenerateReportResponse {
  report: ReviewReport
}

export interface QuizSession {
  sessionId: string
  topic: string
  questions: QuizQuestion[]
  answers: UserAnswer[]
  report?: ReviewReport
}
