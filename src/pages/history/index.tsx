import { useState } from "react"
import { Text, View } from "@tarojs/components"
import Taro, { useLoad } from "@tarojs/taro"

import { ActionButton, Badge, Panel } from "@/components/ui"
import { getFriendlyErrorMessage } from "@/services/api"
import { loadHistoryRecords } from "@/services/history"
import type { LearningRecordSummary } from "@/types/learning"

import "./index.css"

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return `${date.getFullYear()}-${date.getMonth() + 1}-${date.getDate()} ${date.getHours()}:${String(date.getMinutes()).padStart(2, "0")}`
}

export default function HistoryPage() {
  const [records, setRecords] = useState<LearningRecordSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  useLoad(() => {
    requestRecords()
  })

  async function requestRecords() {
    setLoading(true)
    setError("")
    try {
      setRecords(await loadHistoryRecords())
    } catch (err) {
      setError(getFriendlyErrorMessage(err, "历史记录读取失败，请稍后重试"))
    } finally {
      setLoading(false)
    }
  }

  function openRecord(recordId: string) {
    Taro.navigateTo({ url: `/pages/history-detail/index?id=${recordId}` })
  }

  function backHome() {
    Taro.redirectTo({ url: "/pages/index/index" })
  }

  return (
    <View className='screen'>
      <View className='topbar'>
        <Badge tone='green'>学习档案</Badge>
        <Badge tone='blue'>{records.length} 条</Badge>
      </View>
      <View className='hero-title'><Text>以前闯过的关，{"\n"}都在这里。</Text></View>

      {loading ? (
        <Panel tone='soft'>
          <View className='status-copy'><Text>正在读取历史记录...</Text></View>
        </Panel>
      ) : null}

      {error ? (
        <Panel tone='soft'>
          <View className='error-text'><Text>{error}</Text></View>
          <ActionButton tone='secondary' onClick={requestRecords}>重新读取</ActionButton>
        </Panel>
      ) : null}

      {!loading && !error && records.length === 0 ? (
        <Panel tone='soft'>
          <View className='history-empty'><Text>还没有完成过的闯关记录。先生成一组题，完成报告后会自动保存。</Text></View>
          <ActionButton tone='primary' onClick={backHome}>去生成题目</ActionButton>
        </Panel>
      ) : null}

      <View className='history-list'>
        {records.map((record) => (
          <Panel key={record.id} dense>
            <View className='history-card' onClick={() => openRecord(record.id)}>
              <View className='history-card-title'><Text>{record.topic}</Text></View>
              <View className='history-card-meta'>
                <Text>得分 {record.score}</Text>
                <Text>正确率 {record.accuracy}%</Text>
                <Text>{formatDate(record.completedAt)}</Text>
              </View>
            </View>
          </Panel>
        ))}
      </View>
    </View>
  )
}
