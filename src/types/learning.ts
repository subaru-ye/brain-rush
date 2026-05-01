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

export type QuizSessionMode = "normal" | "wrong_review"

export interface QuizSession {
  sessionId: string
  topic: string
  questions: QuizQuestion[]
  answers: UserAnswer[]
  report?: ReviewReport
  mode?: QuizSessionMode
}

export interface AuthSession {
  token: string
  userId: string
}

export interface LearningRecordSummary {
  id: string
  sessionId: string
  topic: string
  score: number
  total: number
  accuracy: number
  completedAt: string
  createdAt: string
}

export interface LearningRecordDetail extends LearningRecordSummary {
  questions: QuizQuestion[]
  answers: UserAnswer[]
  report: ReviewReport
}

export interface HistoryListResponse {
  records: LearningRecordSummary[]
}

export interface HistorySaveResponse {
  record: LearningRecordDetail
}

export type QuestionFeedbackReason =
  | "question_inaccurate"
  | "explanation_unclear"
  | "irrelevant"

export type QuestionFeedbackSource = "quiz" | "report"

export interface QuestionFeedbackRequest {
  sessionId: string
  topic: string
  questionId: string
  reason: QuestionFeedbackReason
  questionSnapshot: QuizQuestion
  selectedIndex?: number
  sourcePage: QuestionFeedbackSource
}

export interface QuestionFeedbackResponse {
  id: string
  createdAt: string
  updatedAt: string
}

export interface WrongQuestionItem {
  recordId: string
  sessionId: string
  topic: string
  questionId: string
  stem: string
  options: string[]
  answerIndex: number
  selectedIndex: number
  explanation: string
  knowledgePoint: string
  userAnswer: string
  correctAnswer: string
  completedAt: string
}

export interface WrongQuestionListResponse {
  items: WrongQuestionItem[]
}
