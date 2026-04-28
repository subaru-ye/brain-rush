import { Text, View } from "@tarojs/components"
import Taro from "@tarojs/taro"

import { ActionButton, Badge } from "@/components/ui"
import { useQuizSession } from "@/hooks/useQuizSession"

import "./index.css"

const optionLabels = ["A", "B", "C", "D"]

export default function QuizPage() {
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
    if (!goNextQuestion()) {
      Taro.navigateTo({ url: "/pages/report/index" })
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
          <ActionButton tone='success' onClick={handleNext}>
            {currentIndex >= session.questions.length - 1 ? "生成学习报告" : "下一题"}
          </ActionButton>
          <View className='full-explain-link'><Text>查看完整解析</Text></View>
        </View>
      ) : null}
    </View>
  )
}
