import { useMemo, useState } from "react"
import { Text, View } from "@tarojs/components"
import Taro, { useLoad } from "@tarojs/taro"

import { ActionButton, Badge, Panel } from "@/components/ui"
import { getCurrentSession, saveCurrentSession } from "@/services/session"
import type { QuizSession, UserAnswer } from "@/types/learning"

import "./index.css"

const optionLabels = ["A", "B", "C", "D"]

export default function QuizPage() {
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
    const firstUnanswered = stored.questions.findIndex(
      (question) => !stored.answers.some((answer) => answer.questionId === question.id)
    )
    setSession(stored)
    setCurrentIndex(firstUnanswered >= 0 ? firstUnanswered : 0)
    setStartedAt(Date.now())
  })

  const question = session?.questions[currentIndex]
  const progress = useMemo(() => {
    if (!session) return 0
    return Math.round(((currentIndex + (answered ? 1 : 0)) / session.questions.length) * 100)
  }, [answered, currentIndex, session])

  function handleSelect(index: number) {
    if (!session || !question || answered) return

    const isCorrect = index === question.answerIndex
    const nextAnswer: UserAnswer = {
      questionId: question.id,
      selectedIndex: index,
      isCorrect,
      elapsedMs: Date.now() - startedAt
    }
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

  function handleNext() {
    if (!session) return
    if (currentIndex >= session.questions.length - 1) {
      Taro.navigateTo({ url: "/pages/report/index" })
      return
    }
    setCurrentIndex((value) => value + 1)
    setSelectedIndex(null)
    setAnswered(false)
    setStartedAt(Date.now())
  }

  function getOptionClass(index: number) {
    if (!answered) return "option"
    if (index === question?.answerIndex) return "option correct"
    if (index === selectedIndex) return "option wrong"
    return "option muted"
  }

  if (!session || !question) {
    return (
      <View className='screen center-screen'>
        <Badge tone='yellow'>读取题目中</Badge>
      </View>
    )
  }

  return (
    <View className='screen quiz-screen'>
      <View className='topbar quiz-topbar'>
        <Badge tone={answered && selectedIndex !== question.answerIndex ? "red" : "green"}>
          第 {currentIndex + 1} / {session.questions.length} 题
        </Badge>
      </View>

      <View className='progress'>
        <View className='progress-fill' style={{ width: `${progress}%` }} />
      </View>

      <View className='question-shell'>
        <View className='knowledge-float'>
          <Badge tone='blue'>知识点：{question.knowledgePoint}</Badge>
        </View>
        <Panel tilt='right'>
          <View className='question-title'><Text>{question.stem}</Text></View>
          <View className='option-list'>
            {question.options.map((option, index) => (
              <View key={option} className={getOptionClass(index)} onClick={() => handleSelect(index)}>
                <View className='option-mark'><Text>{optionLabels[index]}</Text></View>
                <View className='option-text'><Text>{option}</Text></View>
              </View>
            ))}
          </View>
        </Panel>
      </View>

      {answered ? (
        <View className='explain-panel'>
          <Panel tone='soft'>
            <View className='topbar compact'>
              <Badge tone={selectedIndex === question.answerIndex ? "green" : "red"} size='sm'>
                {selectedIndex === question.answerIndex ? "答对啦" : "踩坑啦"}
              </Badge>
              <View className='burst'><Text>解析</Text></View>
            </View>
            <View className='answer-line'>
              <Text>正确答案是 {optionLabels[question.answerIndex]}：{question.options[question.answerIndex]}</Text>
            </View>
            <View className='explain-copy'><Text>{question.explanation}</Text></View>
            <ActionButton tone='success' onClick={handleNext}>
              {currentIndex >= session.questions.length - 1 ? "生成复盘报告" : "下一题"}
            </ActionButton>
          </Panel>
        </View>
      ) : null}
    </View>
  )
}
