"use client";

import { type FC } from "react";

interface KbRetrievalRendererProps {
  args: Record<string, unknown>;
  result?: {
    sources?: Array<{
      content: string;
      source: string;
      score: number;
    }>;
    [key: string]: unknown;
  };
}

export const KbRetrievalRenderer: FC<KbRetrievalRendererProps> = ({ result }) => {
  if (!result?.sources?.length) {
    return (
      <div className="text-sm text-muted-foreground p-3">
        未找到相关知识片段。
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 p-3">
      <div className="text-xs text-muted-foreground font-medium">知识库检索结果</div>
      {result.sources.map((source, idx) => (
        <div key={idx} className="rounded-lg border bg-card p-3 text-sm">
          <div className="whitespace-pre-wrap break-words">{source.content}</div>
          <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
            <span>来源: {source.source}</span>
            <span>相关度: {(source.score * 100).toFixed(0)}%</span>
          </div>
        </div>
      ))}
    </div>
  );
};
