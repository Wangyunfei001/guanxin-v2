"use client"

import * as React from "react"
import { Info, Bot, Wrench, Cpu, RefreshCw, Server } from "lucide-react"
import { toast } from "sonner"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert"
import { useAgentStore } from "@/lib/stores/agent"

export default function AgentPage() {
  const { skills, loading, config, configLoading, loadSkills, loadConfig } =
    useAgentStore()

  React.useEffect(() => {
    loadSkills()
    loadConfig()
  }, [])

  const handleRefresh = () => {
    loadConfig()
    loadSkills()
    toast.success("已刷新")
  }

  // All tools = kb_retrieval + skills as tools
  const allTools = [
    { name: "kb_retrieval", label: "知识库检索", category: "builtin" },
    ...skills.map((s) => ({
      name: `skill__${s.name}`,
      label: s.display_name,
      category: s.category,
    })),
  ]

  return (
    <div className="space-y-4">
      <Alert>
        <Info className="h-4 w-4" />
        <AlertTitle>Agent 配置</AlertTitle>
        <AlertDescription>
          查看 Agent 运行时配置和可用的工具/技能列表。配置来自后端{" "}
          <code className="bg-muted px-1 rounded text-xs">.env</code>。
        </AlertDescription>
      </Alert>

      {/* Model Config */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-sm flex items-center gap-2">
            <Cpu className="h-4 w-4" /> 模型配置
          </CardTitle>
          <Button onClick={handleRefresh} size="sm" variant="outline">
            <RefreshCw className="h-4 w-4" />
            刷新
          </Button>
        </CardHeader>
        <CardContent className="space-y-4">
          {configLoading || !config ? (
            <div className="py-4 text-center text-sm text-muted-foreground">
              加载中...
            </div>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <Label>当前模型</Label>
                  <select
                    className="flex h-9 w-full rounded-md border px-3 py-1 text-sm bg-muted/50 text-muted-foreground cursor-not-allowed"
                    value={config.model}
                    disabled
                  >
                    {config.available_models.map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-muted-foreground">
                    由 <code className="bg-muted px-0.5 rounded text-xs">OPENAI_MODEL</code> 指定
                  </p>
                </div>
                <div className="space-y-1">
                  <Label>Temperature: {config.temperature.toFixed(1)}</Label>
                  <Slider
                    value={[config.temperature]}
                    min={0}
                    max={2}
                    step={0.1}
                    disabled
                  />
                  <p className="text-xs text-muted-foreground">
                    由 <code className="bg-muted px-0.5 rounded text-xs">OPENAI_TEMPERATURE</code> 指定
                  </p>
                </div>
              </div>

              <div className="space-y-1">
                <Label>系统提示词</Label>
                <Textarea
                  value={config.system_prompt}
                  rows={8}
                  readOnly
                  className="bg-muted/30 text-sm font-mono resize-none"
                />
              </div>

              <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                <Badge variant="outline" className="gap-1">
                  <Server className="h-3 w-3" />
                  {config.api_base}
                </Badge>
                <Badge variant="outline">模式: {config.agent_mode}</Badge>
                <Badge variant="outline">
                  工具: {config.tools_count} 个
                </Badge>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Available Tools */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm flex items-center gap-2">
            <Wrench className="h-4 w-4" /> 可用工具（{allTools.length} 个）
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {allTools.map((tool) => (
              <Badge
                key={tool.name}
                variant={
                  tool.category === "builtin" ? "default" : "secondary"
                }
              >
                {tool.label}
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Available Skills (detail) */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">技能详情</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="py-4 text-center text-sm text-muted-foreground">
              加载中...
            </div>
          ) : skills.length === 0 ? (
            <div className="py-4 text-center text-sm text-muted-foreground">
              暂无可用的内置技能
            </div>
          ) : (
            <div className="space-y-2">
              {skills.map((skill) => (
                <div
                  key={skill.name}
                  className="flex items-center gap-3 rounded-md border p-3"
                >
                  <Avatar className="h-8 w-8">
                    <AvatarFallback className="bg-purple-500 text-xs text-white">
                      {skill.display_name[0]}
                    </AvatarFallback>
                  </Avatar>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium">
                      {skill.display_name}
                    </div>
                    <div className="text-xs text-muted-foreground truncate">
                      {skill.description}
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    {skill.tags?.map((t: string) => (
                      <Badge
                        key={t}
                        variant="outline"
                        className="text-[10px]"
                      >
                        {t}
                      </Badge>
                    ))}
                    <Badge variant="secondary" className="text-[10px]">
                      {skill.category}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}