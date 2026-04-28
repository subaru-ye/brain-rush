import type { PropsWithChildren } from "react"
import { Text, View } from "@tarojs/components"

type ReportSectionTone = "default" | "good" | "warn"

interface ReportSectionProps extends PropsWithChildren {
  title: string
  tone?: ReportSectionTone
}

export default function ReportSection({
  title,
  tone = "default",
  children
}: ReportSectionProps) {
  return (
    <View className={["ui-report-section", `ui-report-section--${tone}`].join(" ")}>
      <View className='ui-report-section__title'>
        <Text>{title}</Text>
      </View>
      <View className='ui-report-section__body'>{children}</View>
    </View>
  )
}
