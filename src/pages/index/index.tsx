import { useState } from "react"
import { Text, Textarea, View } from "@tarojs/components"
import Taro from "@tarojs/taro"

import { ActionButton, Panel } from "@/components/ui"
import { generateQuiz, getFriendlyErrorMessage } from "@/services/api"
import { saveCurrentSession } from "@/services/session"

import "./index.css"

const examples = ["JavaScript 闭包", "基金定投", "英语完成时", "面试八股", "AI Agent 入门", "产品经理面试"]

export default function IndexPage() {
  const [inputText, setInputText] = useState("请用 5 道题帮我理解“Python 装饰器”")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

  async function handleGenerate() {
    const normalized = inputText.trim()
    if (!normalized) {
      setError("先把想学的知识点写进来")
      return
    }
    if (normalized.length < 2) {
      setError("学习内容至少需要 2 个字符")
      return
    }

    setLoading(true)
    setError("")
    try {
      const quiz = await generateQuiz(normalized)
      saveCurrentSession({
        sessionId: quiz.sessionId,
        topic: quiz.topic,
        questions: quiz.questions,
        answers: []
      })
      await Taro.navigateTo({ url: "/pages/quiz/index" })
    } catch (err) {
      setError(getFriendlyErrorMessage(err, "题库生成失败，请重试"))
    } finally {
      setLoading(false)
    }
  }

  return (
    <View className='screen index-screen'>
      <View className='hero-title'><Text>今天想把{"\n"}哪个知识点打趴？</Text></View>
      <View className='subcopy'><Text>输入主题，AI 出题。答错也不丢人，讲解会把坑填上。</Text></View>

      <Panel tilt='left'>
        <View className='field-label'><Text>把知识扔进来</Text></View>
        <Textarea
          className='learning-textarea'
          value={inputText}
          maxlength={4000}
          autoHeight
          placeholder='比如：请用 5 道题帮我理解“Python 装饰器”'
          onInput={(event) => setInputText(event.detail.value)}
        />
      </Panel>

      <View className='sticker-stack'>
        {examples.map((item) => (
          <View key={item} className='topic-sticker' onClick={() => setInputText(item)}>
            <Text>{item}</Text>
          </View>
        ))}
      </View>

      {error ? <View className='error-text'><Text>{error}</Text></View> : null}

      <ActionButton tone='primary' loading={loading} disabled={loading} onClick={handleGenerate}>
        {loading ? "LangChain 正在出题..." : "生成闯关题"}
      </ActionButton>
    </View>
  )
}
