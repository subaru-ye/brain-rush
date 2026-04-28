import type { PropsWithChildren } from "react"
import { Text, View } from "@tarojs/components"

type BadgeTone = "yellow" | "green" | "blue" | "red"
type BadgeSize = "md" | "sm"

interface BadgeProps extends PropsWithChildren {
  tone: BadgeTone
  size?: BadgeSize
  compact?: boolean
}

export default function Badge({
  tone,
  size = "md",
  compact = false,
  children
}: BadgeProps) {
  const className = [
    "ui-badge",
    `ui-badge--${tone}`,
    `ui-badge--${size}`,
    compact ? "ui-badge--compact" : ""
  ].filter(Boolean).join(" ")

  return (
    <View className={className}>
      <Text>{children}</Text>
    </View>
  )
}
