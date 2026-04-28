import { Text, View } from "@tarojs/components"
import Taro from "@tarojs/taro"

import { ActionButton, Badge, Panel } from "@/components/ui"
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

  return (
    <View className='screen quiz-screen'>
      <View className='topbar quiz-topbar'>
        <Badge tone={answered && selectedIndex !== question.answerIndex ? "red" : "green"}>
          第 {currentIndex + 1} / {session.questions.length} 题
        </Badge>
      </View>

      <View className='progress'>
        <View className='progress-fill' style={{ width: `${progress}%` }} />
      </View>

      <View className='question-shell'>
        <View className='knowledge-float'>
          <Badge tone='blue'>知识点：{question.knowledgePoint}</Badge>
        </View>
        <Panel tilt='right'>
          <View className='question-title'><Text>{question.stem}</Text></View>
          <View className='option-list'>
            {question.options.map((option, index) => (
              <View key={option} className={getOptionClass(index)} onClick={() => selectAnswer(index)}>
                <View className='option-mark'><Text>{optionLabels[index]}</Text></View>
                <View className='option-text'><Text>{option}</Text></View>
              </View>
            ))}
          </View>
        </Panel>
      </View>

      {answered ? (
        <View className='explain-panel'>
          <Panel tone='soft'>
            <View className='topbar compact'>
              <Badge tone={selectedIndex === question.answerIndex ? "green" : "red"} size='sm'>
                {selectedIndex === question.answerIndex ? "答对啦" : "踩坑啦"}
              </Badge>
              <View className='burst'><Text>解析</Text></View>
            </View>
            <View className='answer-line'>
              <Text>正确答案是 {optionLabels[question.answerIndex]}：{question.options[question.answerIndex]}</Text>
            </View>
            <View className='explain-copy'><Text>{question.explanation}</Text></View>
            <ActionButton tone='success' onClick={handleNext}>
              {currentIndex >= session.questions.length - 1 ? "生成复盘报告" : "下一题"}
            </ActionButton>
          </Panel>
        </View>
      ) : null}
    </View>
  )
}
