"use client"

import * as React from "react"
import { Copy, Check, RotateCcw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

interface ActionsProps {
  content: string
  onRegenerate?: () => void
  className?: string
}

/**
 * Actions bar for messages - copy and regenerate buttons.
 */
export function Actions({ content, onRegenerate, className }: ActionsProps) {
  const [copied, setCopied] = React.useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // clipboard not available
    }
  }

  return (
    <div className={cn("flex items-center gap-1 pt-1", className)}>
      <Button
        variant="ghost"
        size="sm"
        className="h-7 gap-1 text-xs text-muted-foreground"
        onClick={handleCopy}
      >
        {copied ? (
          <Check className="h-3 w-3 text-green-500" />
        ) : (
          <Copy className="h-3 w-3" />
        )}
        {copied ? "已复制" : "复制"}
      </Button>
      {onRegenerate && (
        <Button
          variant="ghost"
          size="sm"
          className="h-7 gap-1 text-xs text-muted-foreground"
          onClick={onRegenerate}
        >
          <RotateCcw className="h-3 w-3" />
          重新生成
        </Button>
      )}
    </div>
  )
}
