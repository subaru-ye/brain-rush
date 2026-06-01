import { useEffect, useRef, useState } from "react"
import { Text, View } from "@tarojs/components"
import Taro from "@tarojs/taro"

import { ActionButton, Badge } from "@/components/ui"
import { useQuizSession } from "@/hooks/useQuizSession"
import { trackEvent } from "@/services/analytics"
import { submitQuestionFeedback } from "@/services/feedback"
import type { QuestionFeedbackReason } from "@/types/learning"
import { formatAnswerText, getAnswerIndexes, getQuestionType } from "@/utils/quiz"

import "./index.css"

const optionLabels = ["A", "B", "C", "D"]

const feedbackOptions: Array<{ reason: QuestionFeedbackReason; label: string }> = [
  { reason: "question_inaccurate", label: "题目不准" },
  { reason: "explanation_unclear", label: "讲解不清楚" },
  { reason: "irrelevant", label: "不相关" }
]

const questionTypeLabels = {
  single_choice: "单选题",
  multiple_choice: "多选题",
  true_false: "判断题"
}

const sourceTypeLabels: Record<string, string> = {
  curated_question: "精选题",
  rag_generated: "RAG生成",
  ai_generated: "AI生成"
}

const showRagDebug = process.env.NODE_ENV !== "production"

export default function QuizPage() {
  const [feedbackStatus, setFeedbackStatus] = useState("")
  const viewedSessionRef = useRef("")
  const {
    session,
    question,
    currentIndex,
    selectedIndexes,
    answered,
    isMultipleChoice,
    isSelectedCorrect,
    selectAnswer,
    submitSelectedAnswer,
    goNextQuestion,
    getOptionClass
  } = useQuizSession()

  useEffect(() => {
    if (!session || viewedSessionRef.current === session.sessionId) return
    viewedSessionRef.current = session.sessionId
    void trackEvent("quiz_view", {
      page: "quiz",
      sessionId: session.sessionId,
      topic: session.topic,
      properties: {
        questionCount: session.questions.length,
        mode: session.mode || "normal",
        retrievalVersion: session.retrievalVersion || ""
      }
    })
  }, [session])

  function handleNext() {
    setFeedbackStatus("")
    if (!goNextQuestion()) {
      if (session) {
        void trackEvent("quiz_completed", {
          page: "quiz",
          sessionId: session.sessionId,
          topic: session.topic,
          properties: {
            questionCount: session.questions.length,
            answeredCount: session.answers.length,
            mode: session.mode || "normal"
          }
        })
      }
      Taro.navigateTo({ url: "/pages/report/index" })
    }
  }

  async function handleFeedback(reason: QuestionFeedbackReason) {
    if (!session || !question || !selectedIndexes.length) return
    setFeedbackStatus("提交中...")
    try {
      await submitQuestionFeedback({
        sessionId: session.sessionId,
        topic: session.topic,
        questionId: question.id,
        reason,
        questionSnapshot: question,
        selectedIndex: selectedIndexes[0],
        selectedIndexes,
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

  const answerIndexes = getAnswerIndexes(question)
  const questionType = getQuestionType(question)

  return (
    <View className='screen quiz-screen'>
      <View className='quiz-status'>
        <View className='quiz-topic'><Text>{question.knowledgePoint}</Text></View>
        <View className='quiz-count'><Text>第 {currentIndex + 1} / {session.questions.length} 题</Text></View>
      </View>

      <View className='question-card'>
        <View className='question-chip'><Text>{questionTypeLabels[questionType]}</Text></View>
        {showRagDebug ? (
          <View className='rag-debug-row'>
            <Text>{sourceTypeLabels[question.sourceType || ""] || question.sourceType || "未知来源"}</Text>
            <Text>{question.retrievalVersion || session.retrievalVersion || "no-retrieval"}</Text>
          </View>
        ) : null}
        <View className='question-title'><Text>{question.stem}</Text></View>
        <View className='question-tip'>
          <Text>{isMultipleChoice ? "请选择所有正确答案，确认后查看解析。" : "请选择一个你认为最准确的答案。"}</Text>
        </View>
      </View>

      <View className='option-list'>
        {question.options.map((option, index) => (
          <View key={`${index}_${option}`} className={getOptionClass(index)} onClick={() => selectAnswer(index)}>
            <View className='option-mark'><Text>{optionLabels[index]}</Text></View>
            <View className='option-text'><Text>{option}</Text></View>
            {answered && answerIndexes.includes(index) ? <View className='option-result correct-mark'><Text>✓</Text></View> : null}
            {answered && selectedIndexes.includes(index) && !answerIndexes.includes(index) ? <View className='option-result wrong-mark'><Text>×</Text></View> : null}
          </View>
        ))}
      </View>

      {isMultipleChoice && !answered ? (
        <ActionButton tone='primary' disabled={!selectedIndexes.length} onClick={submitSelectedAnswer}>
          确认答案
        </ActionButton>
      ) : null}

      {answered ? (
        <View className='answer-card'>
          <View className='answer-card-title'><Text>答案讲解</Text></View>
          <View className='answer-line'>
            <Text>{isSelectedCorrect ? "答对了：" : "正确答案："}{formatAnswerText(question, answerIndexes)}</Text>
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
