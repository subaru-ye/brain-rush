import { useMemo, useState } from "react"
import Taro, { useLoad } from "@tarojs/taro"

import { getCurrentSession, saveCurrentSession } from "@/services/session"
import type { QuizSession } from "@/types/learning"
import {
  createUserAnswer,
  findFirstUnansweredIndex,
  isAnswerCorrect
} from "@/utils/quiz"

export function useQuizSession() {
  const [session, setSession] = useState<QuizSession | null>(null)
  const [currentIndex, setCurrentIndex] = useState(0)
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null)
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

  function selectAnswer(index: number) {
    if (!session || !question || answered) return

    const nextAnswer = createUserAnswer(question, index, startedAt)
    const answers = [
      ...session.answers.filter((answer) => answer.questionId !== question.id),
      nextAnswer
    ]
    const nextSession = { ...session, answers }
    setSelectedIndex(index)
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
    setSelectedIndex(null)
    setAnswered(false)
    setStartedAt(Date.now())
    return true
  }

  function getOptionClass(index: number) {
    if (!answered) return "option"
    if (question && isAnswerCorrect(question, index)) return "option correct"
    if (index === selectedIndex) return "option wrong"
    return "option muted"
  }

  return {
    session,
    question,
    currentIndex,
    selectedIndex,
    answered,
    progress,
    selectAnswer,
    goNextQuestion,
    getOptionClass
  }
}
