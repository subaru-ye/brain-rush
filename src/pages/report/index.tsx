import { useState } from "react"
import { Text, View } from "@tarojs/components"
import Taro, { useLoad } from "@tarojs/taro"

import { ActionButton, Badge, Panel, ReportSection } from "@/components/ui"
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

  function getCorrectCount(nextSession: QuizSession) {
    const questionById = new Map(nextSession.questions.map((question) => [question.id, question]))
    return nextSession.answers.filter((answer) => {
      const question = questionById.get(answer.questionId)
      return question ? answer.selectedIndex === question.answerIndex : false
    }).length
  }

  if (!session) {
    return (
      <View className='screen center-screen'>
        <Badge tone='yellow'>读取报告中</Badge>
      </View>
    )
  }

  if (loading) {
    const correctCount = getCorrectCount(session)
    const accuracy = Math.round((correctCount / session.questions.length) * 100)
    return (
      <View className='screen'>
        <View className='topbar'>
          <Badge tone='blue'>Step 3</Badge>
          <Badge tone='yellow'>POST /api/generate-report</Badge>
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
        <Panel tone='soft'>
          <Badge tone='red' size='sm'>错题包</Badge>
          <View className='api-card'><Text>score: 程序计算，不交给 AI 猜</Text></View>
          <View className='status-row'>
            <View className='spinner' />
            <View className='status-copy'><Text>AI 正在写复盘小纸条...</Text></View>
          </View>
        </Panel>
      </View>
    )
  }

  if (error || !report) {
    return (
      <View className='screen'>
        <View className='hero-title'><Text>报告卡住了</Text></View>
        <View className='subcopy'><Text>{error || "报告生成失败，请重试"}</Text></View>
        <ActionButton tone='primary' onClick={() => requestReport(session)}>
          重新生成报告
        </ActionButton>
      </View>
    )
  }

  return (
    <View className='screen'>
      <View className='topbar'>
        <Badge tone='green'>通关报告</Badge>
        <Badge tone='yellow'>{session.topic}</Badge>
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

      <ReportSection tone='good' title='核心知识点'>
        <View><Text>{report.summary}</Text></View>
      </ReportSection>

      <ReportSection tone='warn' title='薄弱点'>
        <View><Text>{report.weakPoints.length ? report.weakPoints.join("、") : "本轮没有明显薄弱点"}</Text></View>
      </ReportSection>

      {report.wrongQuestions.length ? (
        <ReportSection title='错题回顾'>
          {report.wrongQuestions.map((item) => (
            <View key={item.questionId} className='wrong-review'>
              <View className='wrong-title'><Text>{item.knowledgePoint}</Text></View>
              <View><Text>{item.stem}</Text></View>
              <View className='subcopy'><Text>你的答案：{item.userAnswer}</Text></View>
              <View className='subcopy'><Text>正确答案：{item.correctAnswer}</Text></View>
            </View>
          ))}
        </ReportSection>
      ) : null}

      <ReportSection title='下一步建议'>
        {report.suggestions.map((item) => (
          <View key={item} className='suggestion-item'>
            <Text>· {item}</Text>
          </View>
        ))}
      </ReportSection>

      <View className='footer-actions'>
        <ActionButton tone='secondary' onClick={handleRestart}>再来一局</ActionButton>
        <ActionButton tone='primary'>分享战绩</ActionButton>
      </View>
    </View>
  )
}
