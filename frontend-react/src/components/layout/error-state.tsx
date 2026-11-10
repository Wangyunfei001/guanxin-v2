"use client"

import { WarningCircle } from "@phosphor-icons/react"

import { EmptyState } from "@/components/layout/page-header"
import { Button } from "@/components/ui/button"

/**
 * 数据加载失败时的状态。
 *
 * 统一规则：**空态只在「确实没有数据」时出现**。加载失败要显示错误态
 * 与重试入口，否则网络故障会被渲染成「知识库还是空的」这类谎报。
 */
export function ErrorState({
  message,
  onRetry,
}: {
  message: string
  onRetry?: () => void
}) {
  return (
    <EmptyState
      icon={WarningCircle}
      title="加载失败"
      description={message}
      action={
        onRetry ? (
          <Button size="sm" variant="outline" onClick={onRetry}>
            重试
          </Button>
        ) : undefined
      }
    />
  )
}
