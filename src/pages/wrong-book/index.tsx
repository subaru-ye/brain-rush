import { useState } from "react"
import { Text, View } from "@tarojs/components"
import Taro, { useLoad } from "@tarojs/taro"

import { ActionButton, Badge, Panel } from "@/components/ui"
import { getFriendlyErrorMessage } from "@/services/api"
import { loadWrongQuestions, startWrongQuestionReview } from "@/services/wrongBook"
import type { WrongQuestionItem } from "@/types/learning"

import "./index.css"

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return `${date.getFullYear()}-${date.getMonth() + 1}-${date.getDate()} ${date.getHours()}:${String(date.getMinutes()).padStart(2, "0")}`
}

export default function WrongBookPage() {
  const [items, setItems] = useState<WrongQuestionItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  useLoad(() => {
    requestWrongQuestions()
  })

  async function requestWrongQuestions() {
    setLoading(true)
    setError("")
    try {
      setItems(await loadWrongQuestions())
    } catch (err) {
      setError(getFriendlyErrorMessage(err, "错题本读取失败，请稍后重试"))
    } finally {
      setLoading(false)
    }
  }

  function startReview() {
    if (!items.length) return
    startWrongQuestionReview(items)
    Taro.navigateTo({ url: "/pages/quiz/index" })
  }

  function backHome() {
    Taro.redirectTo({ url: "/pages/index/index" })
  }

  return (
    <View className='screen wrong-book-screen'>
      <View className='wrong-book-status'>
        <Badge tone='green'>错题本</Badge>
        <View className='wrong-book-count'><Text>{items.length} 道</Text></View>
      </View>

      <View className='hero-title'><Text>把错题再打一遍</Text></View>
      <View className='subcopy'><Text>这里从历史记录里聚合答错的题，复训不会重新消耗 AI 额度。</Text></View>

      {loading ? (
        <Panel tone='soft'>
          <View className='status-copy'><Text>正在整理错题...</Text></View>
        </Panel>
      ) : null}

      {error ? (
        <Panel tone='soft'>
          <View className='error-text'><Text>{error}</Text></View>
          <ActionButton tone='secondary' onClick={requestWrongQuestions}>重新读取</ActionButton>
        </Panel>
      ) : null}

      {!loading && !error && items.length === 0 ? (
        <Panel tone='soft'>
          <View className='wrong-book-empty'><Text>还没有错题。完成一次学习报告后，答错的题会自动出现在这里。</Text></View>
          <ActionButton tone='primary' onClick={backHome}>去生成题目</ActionButton>
        </Panel>
      ) : null}

      {!loading && !error && items.length > 0 ? (
        <>
          <View className='wrong-book-actions'>
            <ActionButton tone='primary' onClick={startReview}>再练这些错题</ActionButton>
          </View>

          <View className='wrong-question-list'>
            {items.map((item) => (
              <Panel key={`${item.recordId}_${item.questionId}`} dense>
                <View className='wrong-question-card'>
                  <View className='wrong-question-meta'>
                    <Text>{item.topic}</Text>
                    <Text>{formatDate(item.completedAt)}</Text>
                  </View>
                  <View className='wrong-question-point'><Text>{item.knowledgePoint}</Text></View>
                  <View className='wrong-question-stem'><Text>{item.stem}</Text></View>
                  <View className='wrong-answer-grid'>
                    <View>
                      <Text>你的答案</Text>
                      <Text>{item.userAnswer}</Text>
                    </View>
                    <View>
                      <Text>正确答案</Text>
                      <Text>{item.correctAnswer}</Text>
                    </View>
                  </View>
                </View>
              </Panel>
            ))}
          </View>
        </>
      ) : null}
    </View>
  )
}
