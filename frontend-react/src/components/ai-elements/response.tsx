"use client"

import * as React from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import rehypeHighlight from "rehype-highlight"
import { cn } from "@/lib/utils"
import { CodeBlock } from "./code-block"
import type { BundledLanguage } from "shiki"

interface ResponseProps {
  content: string
  className?: string
}

/**
 * Response component - renders Markdown content with streaming support.
 * Uses react-markdown + remark-gfm + rehype-highlight for rich rendering.
 * Code blocks are rendered with the CodeBlock component (syntax highlight + copy).
 */
export function Response({ content, className }: ResponseProps) {
  if (!content) return null

  return (
    <div
      className={cn("max-w-none break-words text-sm leading-relaxed", className)}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{
          pre: ({ children }) => <>{children}</>,
          code: ({ className, children, node, ...props }) => {
            const match = /language-(\w+)/.exec(className || "")
            const isBlock = match && typeof children === "string"
            if (isBlock) {
              return (
                <CodeBlock
                  language={match[1] as BundledLanguage}
                  code={String(children).replace(/\n$/, "")}
                />
              )
            }
            return (
              <code
                className={cn(
                  "rounded bg-muted px-1.5 py-0.5 text-xs",
                  className,
                )}
                {...props}
              >
                {children}
              </code>
            )
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
