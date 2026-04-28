import type { PropsWithChildren } from "react"
import { View } from "@tarojs/components"

type PanelTone = "default" | "soft"
type PanelTilt = "none" | "left" | "right"

interface PanelProps extends PropsWithChildren {
  tone?: PanelTone
  tilt?: PanelTilt
  dense?: boolean
}

export default function Panel({
  tone = "default",
  tilt = "none",
  dense = false,
  children
}: PanelProps) {
  const className = [
    "ui-panel",
    `ui-panel--${tone}`,
    tilt !== "none" ? `ui-panel--tilt-${tilt}` : "",
    dense ? "ui-panel--dense" : ""
  ].filter(Boolean).join(" ")

  return <View className={className}>{children}</View>
}
