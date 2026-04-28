import type { PropsWithChildren } from "react"
import { Button, Text } from "@tarojs/components"

type ActionButtonTone = "primary" | "success" | "secondary"

interface ActionButtonProps extends PropsWithChildren {
  tone: ActionButtonTone
  disabled?: boolean
  loading?: boolean
  onClick?: () => void | Promise<void>
}

export default function ActionButton({
  tone,
  disabled = false,
  loading = false,
  onClick,
  children
}: ActionButtonProps) {
  const className = ["ui-button", `ui-button--${tone}`].join(" ")

  return (
    <Button
      className={className}
      loading={loading}
      disabled={disabled || loading}
      onClick={onClick}
    >
      <Text>{children}</Text>
    </Button>
  )
}
