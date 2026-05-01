import { useState } from "react"
import { Text, View } from "@tarojs/components"
import Taro from "@tarojs/taro"

import { ActionButton, Badge } from "@/components/ui"
import { useQuizSession } from "@/hooks/useQuizSession"
import { submitQuestionFeedback } from "@/services/feedback"
import type { QuestionFeedbackReason } from "@/types/learning"

import "./index.css"

const optionLabels = ["A", "B", "C", "D"]

const feedbackOptions: Array<{ reason: QuestionFeedbackReason; label: string }> = [
  { reason: "question_inaccurate", label: "题目不准" },
  { reason: "explanation_unclear", label: "讲解不清楚" },
  { reason: "irrelevant", label: "不相关" }
]

export default function QuizPage() {
  const [feedbackStatus, setFeedbackStatus] = useState("")
  const {
    session,
    question,
    currentIndex,
    selectedIndex,
    answered,
    progress,
    selectAnswer,
    goNextQuestion,
    getOptionClass
  } = useQuizSession()

  function handleNext() {
    setFeedbackStatus("")
    if (!goNextQuestion()) {
      Taro.navigateTo({ url: "/pages/report/index" })
    }
  }

  async function handleFeedback(reason: QuestionFeedbackReason) {
    if (!session || !question || selectedIndex === null) return
    setFeedbackStatus("提交中...")
    try {
      await submitQuestionFeedback({
        sessionId: session.sessionId,
        topic: session.topic,
        questionId: question.id,
        reason,
        questionSnapshot: question,
        selectedIndex,
        sourcePage: "quiz"
      })
      setFeedbackStatus("已收到反馈")
    } catch {
      setFeedbackStatus("反馈提交失败，请稍后再试")
    }
  }

  if (!session || !question) {
    return (
      <View className='screen center-screen'>
        <Badge tone='yellow'>读取题目中</Badge>
      </View>
    )
  }

  const isCorrect = selectedIndex === question.answerIndex

  return (
    <View className='screen quiz-screen'>
      <View className='quiz-status'>
        <View className='quiz-topic'><Text>{question.knowledgePoint}</Text></View>
        <View className='quiz-count'><Text>第 {currentIndex + 1} / {session.questions.length} 题</Text></View>
      </View>

      <View className='question-card'>
        <View className='question-chip'><Text>{question.options.length > 1 ? "单选题" : "判断题"}</Text></View>
        <View className='question-title'><Text>{question.stem}</Text></View>
        <View className='question-tip'><Text>请选择一个你认为最准确的答案。</Text></View>
      </View>

      <View className='option-list'>
        {question.options.map((option, index) => (
          <View key={option} className={getOptionClass(index)} onClick={() => selectAnswer(index)}>
            <View className='option-mark'><Text>{optionLabels[index]}</Text></View>
            <View className='option-text'><Text>{option}</Text></View>
            {answered && index === question.answerIndex ? <View className='option-result correct-mark'><Text>✓</Text></View> : null}
            {answered && index === selectedIndex && !isCorrect ? <View className='option-result wrong-mark'><Text>×</Text></View> : null}
          </View>
        ))}
      </View>

      {answered ? (
        <View className='answer-card'>
          <View className='answer-card-title'><Text>答案讲解</Text></View>
          <View className='answer-line'>
            <Text>正确答案：{optionLabels[question.answerIndex]}，{question.options[question.answerIndex]}</Text>
          </View>
          <View className='explain-copy'><Text>{question.explanation}</Text></View>
          <View className='feedback-row'>
            {feedbackOptions.map((item) => (
              <View
                key={item.reason}
                className='feedback-chip'
                onClick={() => handleFeedback(item.reason)}
              >
                <Text>{item.label}</Text>
              </View>
            ))}
          </View>
          {feedbackStatus ? <View className='feedback-notice'><Text>{feedbackStatus}</Text></View> : null}
          <ActionButton tone='success' onClick={handleNext}>
            {currentIndex >= session.questions.length - 1 ? "生成学习报告" : "下一题"}
          </ActionButton>
          <View className='full-explain-link'><Text>查看完整解析</Text></View>
        </View>
      ) : null}
    </View>
  )
}
