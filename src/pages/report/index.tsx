import { useState } from "react"
import { Button, Text, View } from "@tarojs/components"
import Taro, { useLoad } from "@tarojs/taro"

import { generateReport } from "@/services/api"
import { clearCurrentSession, getCurrentSession, saveCurrentSession } from "@/services/session"
import type { QuizSession, ReviewReport } from "@/types/learning"

import "./index.css"

export default function ReportPage() {
  const [session, setSession] = useState<QuizSession | null>(null)
  const [report, setReport] = useState<ReviewReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

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
    try {
      const response = await generateReport(nextSession.topic, nextSession.questions, nextSession.answers)
      const storedSession = { ...nextSession, report: response.report }
      setReport(response.report)
      setSession(storedSession)
      saveCurrentSession(storedSession)
    } catch (err) {
      setError(err instanceof Error ? err.message : "报告生成失败，请重试")
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
        <View className='badge yellow'><Text>读取报告中</Text></View>
      </View>
    )
  }

  if (loading) {
    const correctCount = session.answers.filter((answer) => answer.isCorrect).length
    const accuracy = Math.round((correctCount / session.questions.length) * 100)
    return (
      <View className='screen'>
        <View className='topbar'>
          <View className='badge blue'><Text>Step 3</Text></View>
          <View className='badge yellow'><Text>POST /api/generate-report</Text></View>
        </View>
        <View className='hero-title'><Text>答完啦，{"\n"}该复盘了。</Text></View>
        <View className='subcopy'><Text>前端把真实答题结果交给报告接口，AI 只负责总结，不负责乱编分数。</Text></View>
        <View className='score-box'>
          <View className='score-item'>
            <View className='score-number'>
              <Text>{correctCount}/{session.questions.length}</Text>
            </View>
            <View><Text>答对题数</Text></View>
          </View>
          <View className='score-item'>
            <View className='score-number'><Text>{accuracy}%</Text></View>
            <View><Text>正确率</Text></View>
          </View>
        </View>
        <View className='comic-panel'>
          <View className='badge red'><Text>错题包</Text></View>
          <View className='api-card'><Text>score: 程序计算，不交给 AI 猜</Text></View>
          <View className='status-row'>
            <View className='spinner' />
            <View className='status-copy'><Text>AI 正在写复盘小纸条...</Text></View>
          </View>
        </View>
      </View>
    )
  }

  if (error || !report) {
    return (
      <View className='screen'>
        <View className='hero-title'><Text>报告卡住了</Text></View>
        <View className='subcopy'><Text>{error || "报告生成失败，请重试"}</Text></View>
        <Button className='comic-button' onClick={() => requestReport(session)}>
          <Text>重新生成报告</Text>
        </Button>
      </View>
    )
  }

  return (
    <View className='screen'>
      <View className='topbar'>
        <View className='badge green'><Text>通关报告</Text></View>
        <View className='badge yellow'><Text>{session.topic}</Text></View>
      </View>
      <View className='hero-title'><Text>这回没白学，{"\n"}你掌握 {report.accuracy}%。</Text></View>

      <View className='score-box'>
        <View className='score-item green-bg'>
          <View className='score-number'><Text>{report.score}</Text></View>
          <View><Text>本轮得分</Text></View>
        </View>
        <View className='score-item yellow-bg'>
          <View className='score-number'><Text>{report.wrongQuestions.length}</Text></View>
          <View><Text>需要复习</Text></View>
        </View>
      </View>

      <View className='report-section good'>
        <View className='report-title'><Text>核心知识点</Text></View>
        <View><Text>{report.summary}</Text></View>
      </View>

      <View className='report-section warn'>
        <View className='report-title'><Text>薄弱点</Text></View>
        <View><Text>{report.weakPoints.length ? report.weakPoints.join("、") : "本轮没有明显薄弱点"}</Text></View>
      </View>

      {report.wrongQuestions.length ? (
        <View className='report-section'>
          <View className='report-title'><Text>错题回顾</Text></View>
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

      <View className='report-section'>
        <View className='report-title'><Text>下一步建议</Text></View>
        {report.suggestions.map((item) => (
          <View key={item} className='suggestion-item'>
            <Text>· {item}</Text>
          </View>
        ))}
      </View>

      <View className='footer-actions'>
        <Button className='comic-button secondary' onClick={handleRestart}>
          <Text>再来一局</Text>
        </Button>
        <Button className='comic-button'><Text>分享战绩</Text></Button>
      </View>
    </View>
  )
}
