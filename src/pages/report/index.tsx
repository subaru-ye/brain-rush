import { useState } from "react"
import { Text, View } from "@tarojs/components"
import Taro, { useLoad } from "@tarojs/taro"

import { ActionButton, Badge } from "@/components/ui"
import { generateReport, getFriendlyErrorMessage } from "@/services/api"
import { saveLearningRecordToHistory } from "@/services/history"
import { clearCurrentSession, getCurrentSession, saveCurrentSession } from "@/services/session"
import type { QuizSession, ReviewReport } from "@/types/learning"
import { getAccuracyPercent, getCorrectCount } from "@/utils/quiz"

import "./index.css"

export default function ReportPage() {
  const [session, setSession] = useState<QuizSession | null>(null)
  const [report, setReport] = useState<ReviewReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [historyNotice, setHistoryNotice] = useState("")

  useLoad(() => {
    const stored = getCurrentSession()
    if (!stored) {
      Taro.redirectTo({ url: "/pages/index/index" })
      return
    }
    setSession(stored)
    if (stored.report) {
      setReport(stored.report)
      setLoading(false)
      return
    }
    requestReport(stored)
  })

  async function requestReport(nextSession: QuizSession) {
    setLoading(true)
    setError("")
    setHistoryNotice("")
    try {
      const response = await generateReport(nextSession.topic, nextSession.questions, nextSession.answers)
      const storedSession = { ...nextSession, report: response.report }
      setReport(response.report)
      setSession(storedSession)
      saveCurrentSession(storedSession)
      try {
        await saveLearningRecordToHistory(storedSession)
      } catch {
        setHistoryNotice("报告已生成，但历史记录保存失败，稍后可重新生成报告再保存")
      }
    } catch (err) {
      setError(getFriendlyErrorMessage(err, "报告生成失败，请重试"))
    } finally {
      setLoading(false)
    }
  }

  function handleRestart() {
    clearCurrentSession()
    Taro.redirectTo({ url: "/pages/index/index" })
  }

  if (!session) {
    return (
      <View className='screen center-screen'>
        <Badge tone='yellow'>读取报告中</Badge>
      </View>
    )
  }

  if (loading) {
    const correctCount = getCorrectCount(session.questions, session.answers)
    const accuracy = getAccuracyPercent(session.questions, session.answers)
    return (
      <View className='screen report-screen'>
        <View className='report-status'>
          <Badge tone='green'>本次掌握度</Badge>
          <View className='report-status-copy'><Text>生成中</Text></View>
        </View>
        <View className='hero-title'><Text>正在整理报告</Text></View>
        <View className='subcopy'><Text>先统计答题结果，再把重点和错题整理成复习卡。</Text></View>
        <View className='report-summary-card'>
          <View className='score-ring'><Text>{accuracy}%</Text></View>
          <View className='summary-copy'>
            <View className='summary-topic'><Text>{session.topic}</Text></View>
            <View className='summary-desc'><Text>已答对 {correctCount} / {session.questions.length}，AI 正在补充复盘建议。</Text></View>
          </View>
        </View>
      </View>
    )
  }

  if (error || !report) {
    return (
      <View className='screen report-screen'>
        <View className='hero-title'><Text>报告没生成</Text></View>
        <View className='subcopy'><Text>{error || "报告生成失败，请重试"}</Text></View>
        <ActionButton tone='primary' onClick={() => requestReport(session)}>
          重新生成报告
        </ActionButton>
      </View>
    )
  }

  const correctCount = getCorrectCount(session.questions, session.answers)
  const weakPoints = report.weakPoints.length ? report.weakPoints : ["本轮没有明显薄弱点"]
  const memoryItems = [
    report.summary,
    ...weakPoints,
    ...(report.suggestions.length ? report.suggestions : ["再练一轮错题，巩固记忆。"])
  ].slice(0, 3)

  return (
    <View className='screen report-screen'>
      <View className='report-status'>
        <Badge tone='green'>本次掌握度</Badge>
        <View className='report-status-copy'><Text>已完成</Text></View>
      </View>

      <View className='hero-title'><Text>本次学习报告</Text></View>
      <View className='subcopy'><Text>报告先给结论，再给重点，避免一屏塞太多信息。</Text></View>

      <View className='report-summary-card'>
        <View className='score-ring'><Text>{report.accuracy}%</Text></View>
        <View className='summary-copy'>
          <View className='summary-topic'><Text>{session.topic}</Text></View>
          <View className='summary-desc'><Text>{report.summary}</Text></View>
          <View className='summary-tags'>
            <View><Text>答对 {correctCount} / {session.questions.length}</Text></View>
            <View><Text>错题 {report.wrongQuestions.length}</Text></View>
          </View>
        </View>
      </View>

      <View className='memory-card'>
        <View className='section-title'><Text>这次记住 3 件事</Text></View>
        {memoryItems.map((item) => (
          <View key={item} className='memory-item'>
            <Text>• {item}</Text>
          </View>
        ))}
      </View>

      {report.wrongQuestions.length ? (
        <View className='memory-card'>
          <View className='section-title'><Text>错题回顾</Text></View>
          {report.wrongQuestions.map((item) => (
            <View key={item.questionId} className='wrong-review'>
              <View className='wrong-title'><Text>{item.knowledgePoint}</Text></View>
              <View><Text>{item.stem}</Text></View>
              <View className='subcopy'><Text>你的答案：{item.userAnswer}</Text></View>
              <View className='subcopy'><Text>正确答案：{item.correctAnswer}</Text></View>
            </View>
          ))}
        </View>
      ) : null}

      <View className='poster-card'>
        <View className='poster-title'><Text>分享海报</Text></View>
        <View className='poster-copy'><Text>把知识做成关卡，记忆会更深。</Text></View>
        <View className='poster-icon'>
          <View /><View /><View />
          <View /><View /><View />
          <View /><View /><View />
        </View>
      </View>

      <View className='report-actions'>
        <ActionButton tone='primary'>生成海报</ActionButton>
        <ActionButton tone='secondary' onClick={handleRestart}>再练一轮错题</ActionButton>
      </View>
      {historyNotice ? <View className='history-notice'><Text>{historyNotice}</Text></View> : null}
    </View>
  )
}
