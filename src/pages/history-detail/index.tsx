import { useState } from "react"
import { Text, View } from "@tarojs/components"
import Taro, { useLoad } from "@tarojs/taro"

import { ActionButton, Badge, Panel, ReportSection } from "@/components/ui"
import { getFriendlyErrorMessage } from "@/services/api"
import { loadHistoryRecord } from "@/services/history"
import type { LearningRecordDetail } from "@/types/learning"

import "./index.css"

export default function HistoryDetailPage() {
  const [record, setRecord] = useState<LearningRecordDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [recordId, setRecordId] = useState("")

  useLoad((options) => {
    const id = typeof options.id === "string" ? options.id : ""
    setRecordId(id)
    if (!id) {
      setError("历史记录不存在")
      setLoading(false)
      return
    }
    requestRecord(id)
  })

  async function requestRecord(id = recordId) {
    if (!id) {
      return
    }
    setLoading(true)
    setError("")
    try {
      setRecord(await loadHistoryRecord(id))
    } catch (err) {
      setError(getFriendlyErrorMessage(err, "历史详情读取失败，请稍后重试"))
    } finally {
      setLoading(false)
    }
  }

  function backHistory() {
    Taro.redirectTo({ url: "/pages/history/index" })
  }

  if (loading) {
    return (
      <View className='screen'>
        <Panel tone='soft'>
          <View className='status-copy'><Text>正在读取历史详情...</Text></View>
        </Panel>
      </View>
    )
  }

  if (error || !record) {
    return (
      <View className='screen'>
        <View className='hero-title'><Text>记录没读到</Text></View>
        <View className='subcopy'><Text>{error || "历史详情读取失败，请稍后重试"}</Text></View>
        <ActionButton tone='secondary' onClick={() => requestRecord()}>重新读取</ActionButton>
      </View>
    )
  }

  return (
    <View className='screen'>
      <View className='topbar'>
        <Badge tone='green'>历史详情</Badge>
        <Badge tone='yellow'>{record.topic}</Badge>
      </View>
      <View className='hero-title'><Text>这次闯关，{"\n"}得分 {record.score}。</Text></View>

      <View className='history-detail-meta'>
        <Badge tone='blue'>正确率 {record.accuracy}%</Badge>
        <Badge tone='yellow'>共 {record.total} 题</Badge>
      </View>

      <ReportSection tone='good' title='核心总结'>
        <View><Text>{record.report.summary}</Text></View>
      </ReportSection>

      <ReportSection tone='warn' title='薄弱点'>
        <View><Text>{record.report.weakPoints.length ? record.report.weakPoints.join("、") : "本轮没有明显薄弱点"}</Text></View>
      </ReportSection>

      {record.report.wrongQuestions.length ? (
        <ReportSection title='错题回顾'>
          {record.report.wrongQuestions.map((item) => (
            <View key={item.questionId} className='wrong-review'>
              <View className='wrong-title'><Text>{item.knowledgePoint}</Text></View>
              <View><Text>{item.stem}</Text></View>
              <View className='subcopy'><Text>你的答案：{item.userAnswer}</Text></View>
              <View className='subcopy'><Text>正确答案：{item.correctAnswer}</Text></View>
            </View>
          ))}
        </ReportSection>
      ) : null}

      <ActionButton tone='secondary' onClick={backHistory}>返回历史列表</ActionButton>
    </View>
  )
}
