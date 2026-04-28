import { useState } from "react"
import { Text, Textarea, View } from "@tarojs/components"
import Taro from "@tarojs/taro"

import { ActionButton, Panel } from "@/components/ui"
import { generateQuiz, getFriendlyErrorMessage } from "@/services/api"
import { saveCurrentSession } from "@/services/session"

import "./index.css"

const examples = ["AI 基础", "面试知识点", "产品入门", "RAG 入门", "英语语法", "基金定投"]

const sampleTopics = [
  {
    title: "RAG 是什么？和传统搜索有什么区别？",
    prompt: "我想快速搞懂 RAG 和传统搜索的区别。"
  },
  {
    title: "AI Agent 入门",
    prompt: "请用 5 道题帮我理解 AI Agent 的定义、核心能力和典型应用。"
  },
  {
    title: "产品经理面试",
    prompt: "帮我用 5 道题复习产品经理面试里的需求分析、优先级和指标设计。"
  }
]

export default function IndexPage() {
  const [sampleIndex, setSampleIndex] = useState(0)
  const [inputText, setInputText] = useState(sampleTopics[0].prompt)
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

  function handleOpenHistory() {
    Taro.navigateTo({ url: "/pages/history/index" })
  }

  function handleUseExample(text: string) {
    setInputText(text)
    setError("")
  }

  function handleNextSample() {
    const nextIndex = (sampleIndex + 1) % sampleTopics.length
    setSampleIndex(nextIndex)
    handleUseExample(sampleTopics[nextIndex].prompt)
  }

  const activeSample = sampleTopics[sampleIndex]

  return (
    <View className='screen index-screen'>
      <View className='index-toolbar'>
        <View className='index-mode-pill'><Text>新建学习</Text></View>
        <View className='index-ready-copy'><Text>已为你准备 {sampleTopics.length} 个示例</Text></View>
      </View>

      <View className='index-hero'>
        <View className='index-hero-copy'>
          <View className='hero-title'><Text>想学什么？</Text></View>
          <View className='subcopy'><Text>输入一句话、一段文字，AI 会自动整理成一组可闯关的题目。</Text></View>
        </View>
        <View className='mascot-orb'>
          <View className='mascot-eye' />
          <View className='mascot-smile' />
        </View>
      </View>

      <View className='sample-card' onClick={() => handleUseExample(activeSample.prompt)}>
        <View className='sample-dot'>
          <View className='sample-dot-core' />
        </View>
        <View className='sample-content'>
          <View className='sample-label'><Text>示例主题</Text></View>
          <View className='sample-title'><Text>{activeSample.title}</Text></View>
        </View>
      </View>

      <Panel>
        <View className='field-label'><Text>学习内容</Text></View>
        <Textarea
          className='learning-textarea'
          value={inputText}
          maxlength={4000}
          autoHeight={false}
          placeholder='比如：我想快速搞懂什么是 RAG，它和传统搜索有什么区别？'
          onInput={(event) => setInputText(event.detail.value)}
        />
      </Panel>

      <View className='sticker-stack'>
        {examples.map((item) => (
          <View key={item} className='topic-sticker' onClick={() => handleUseExample(item)}>
            <Text>{item}</Text>
          </View>
        ))}
      </View>

      {error ? <View className='error-text'><Text>{error}</Text></View> : null}

      <ActionButton tone='primary' loading={loading} disabled={loading} onClick={handleGenerate}>
        {loading ? "正在生成题目..." : "开始生成"}
      </ActionButton>

      <View className='sample-switch' onClick={handleNextSample}>
        <Text>换个示例</Text>
      </View>

      <View className='progress-card'>
        <View className='progress-card-title'><Text>生成进度</Text></View>
        <View className='soft-progress'>
          <View className={`soft-progress-fill ${loading ? "is-loading" : ""}`} />
        </View>
        <View className='progress-steps'>
          <View><Text>已清洗输入</Text></View>
          <View><Text>{loading ? "正在出题" : "准备出题"}</Text></View>
          <View><Text>准备返回</Text></View>
        </View>
      </View>

      <View className='index-stats'>
        <View className='index-stat'>
          <View className='index-stat-number'><Text>5题</Text></View>
          <View className='index-stat-label'><Text>默认题量</Text></View>
        </View>
        <View className='index-stat'>
          <View className='index-stat-number'><Text>3类</Text></View>
          <View className='index-stat-label'><Text>题型组合</Text></View>
        </View>
        <View className='index-stat'>
          <View className='index-stat-number'><Text>1份</Text></View>
          <View className='index-stat-label'><Text>学习报告</Text></View>
        </View>
      </View>

      <View className='history-entry'>
        <ActionButton tone='secondary' onClick={handleOpenHistory}>
          查看历史记录
        </ActionButton>
      </View>
    </View>
  )
}
