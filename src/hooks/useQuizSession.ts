import { useMemo, useState } from "react"
import Taro, { useLoad } from "@tarojs/taro"

import { getCurrentSession, saveCurrentSession } from "@/services/session"
import type { QuizSession } from "@/types/learning"
import {
  createUserAnswer,
  findFirstUnansweredIndex,
  getAnswerIndexes,
  getQuestionType,
  isAnswerCorrectByIndexes
} from "@/utils/quiz"

export function useQuizSession() {
  const [session, setSession] = useState<QuizSession | null>(null)
  const [currentIndex, setCurrentIndex] = useState(0)
  const [selectedIndexes, setSelectedIndexes] = useState<number[]>([])
  const [answered, setAnswered] = useState(false)
  const [startedAt, setStartedAt] = useState(Date.now())

  useLoad(() => {
    const stored = getCurrentSession()
    if (!stored) {
      Taro.redirectTo({ url: "/pages/index/index" })
      return
    }
    const firstUnanswered = findFirstUnansweredIndex(stored.questions, stored.answers)
    setSession(stored)
    setCurrentIndex(firstUnanswered >= 0 ? firstUnanswered : 0)
    setStartedAt(Date.now())
  })

  const question = session?.questions[currentIndex]
  const progress = useMemo(() => {
    if (!session) return 0
    return Math.round(((currentIndex + (answered ? 1 : 0)) / session.questions.length) * 100)
  }, [answered, currentIndex, session])

  const isMultipleChoice = question ? getQuestionType(question) === "multiple_choice" : false

  function selectAnswer(index: number) {
    if (!session || !question || answered) return
    if (isMultipleChoice) {
      setSelectedIndexes((value) => (
        value.includes(index)
          ? value.filter((item) => item !== index)
          : [...value, index].sort((a, b) => a - b)
      ))
      return
    }

    submitAnswer([index])
  }

  function submitSelectedAnswer() {
    if (!selectedIndexes.length) return
    submitAnswer(selectedIndexes)
  }

  function submitAnswer(indexes: number[]) {
    if (!session || !question || answered) return

    const nextAnswer = createUserAnswer(question, indexes, startedAt)
    const answers = [
      ...session.answers.filter((answer) => answer.questionId !== question.id),
      nextAnswer
    ]
    const nextSession = { ...session, answers }
    setSelectedIndexes(nextAnswer.selectedIndexes || [])
    setAnswered(true)
    setSession(nextSession)
    saveCurrentSession(nextSession)
  }

  function goNextQuestion(): boolean {
    if (!session) return false
    if (currentIndex >= session.questions.length - 1) {
      return false
    }
    setCurrentIndex((value) => value + 1)
    setSelectedIndexes([])
    setAnswered(false)
    setStartedAt(Date.now())
    return true
  }

  function getOptionClass(index: number) {
    const selected = selectedIndexes.includes(index)
    if (!answered) return selected ? "option selected" : "option"
    if (question && getAnswerIndexes(question).includes(index)) return "option correct"
    if (selected) return "option wrong"
    return "option muted"
  }

  return {
    session,
    question,
    currentIndex,
    selectedIndex: selectedIndexes[0] ?? null,
    selectedIndexes,
    answered,
    progress,
    isMultipleChoice,
    isSelectedCorrect: question ? isAnswerCorrectByIndexes(question, selectedIndexes) : false,
    selectAnswer,
    submitSelectedAnswer,
    goNextQuestion,
    getOptionClass
  }
}
