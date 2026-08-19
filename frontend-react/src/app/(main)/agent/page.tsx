"use client"

import * as React from "react"
import { Info, Wrench, Cpu, RefreshCw, Server, Save } from "lucide-react"
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
import { useAuthStore } from "@/lib/stores/auth"
import { Input } from "@/components/ui/input"
import type { AgentConfig } from "@/types"

export default function AgentPage() {
  const { skills, loading, config, configLoading, saving, loadSkills, loadConfig, saveConfig } =
    useAgentStore()
  const isAdmin = useAuthStore((state) => state.isAdmin)
  const [draft, setDraft] = React.useState<AgentConfig | null>(null)

  React.useEffect(() => {
    loadSkills()
    loadConfig()
  }, [loadConfig, loadSkills])

  React.useEffect(() => {
    if (config) setDraft(structuredClone(config))
  }, [config])

  const handleRefresh = () => {
    loadConfig()
    loadSkills()
    toast.success("已刷新")
  }

  const toggleListValue = (
    key: "enabled_tools" | "enabled_skills" | "mcp_servers",
    value: string,
  ) => {
    setDraft((current) => {
      if (!current) return current
      const values = current[key]
      return {
        ...current,
        [key]: values.includes(value)
          ? values.filter((item) => item !== value)
          : [...values, value],
      }
    })
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
          {isAdmin ? "编辑当前租户的持久化 Agent 配置。" : "当前账号为只读模式；仅管理员可以修改配置。"}
        </AlertDescription>
      </Alert>

      {/* Model Config */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-sm flex items-center gap-2">
            <Cpu className="h-4 w-4" /> 模型配置
          </CardTitle>
          <div className="flex gap-2">
            {isAdmin && draft && (
              <Button
                size="sm"
                disabled={saving}
                onClick={async () => {
                  await saveConfig(draft)
                  toast.success("配置已保存，将在下一轮对话生效")
                }}
              >
                <Save className="h-4 w-4" /> 保存
              </Button>
            )}
            <Button onClick={handleRefresh} size="sm" variant="outline">
              <RefreshCw className="h-4 w-4" /> 恢复服务器值
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {configLoading || !draft ? (
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
                    value={draft.model}
                    disabled={!isAdmin}
                    onChange={(event) => setDraft({ ...draft, model: event.target.value })}
                  >
                    {draft.available_models.map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-muted-foreground">
                    必须选择服务器允许的模型
                  </p>
                </div>
                <div className="space-y-1">
                  <Label>Temperature: {draft.temperature.toFixed(1)}</Label>
                  <Slider
                    value={[draft.temperature]}
                    min={0}
                    max={2}
                    step={0.1}
                    disabled={!isAdmin}
                    onValueChange={([temperature]) => setDraft({ ...draft, temperature })}
                  />
                  <p className="text-xs text-muted-foreground">
                    允许范围 0–2
                  </p>
                </div>
              </div>

              <div className="space-y-1">
                <Label>系统提示词</Label>
                <Textarea
                  value={draft.system_prompt}
                  rows={8}
                  readOnly={!isAdmin}
                  onChange={(event) => setDraft({ ...draft, system_prompt: event.target.value })}
                  className="bg-muted/30 text-sm font-mono resize-none"
                />
              </div>

              <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                <Badge variant="outline" className="gap-1">
                  <Server className="h-3 w-3" />
                  {draft.api_base}
                </Badge>
                <Badge variant="outline">模式: {draft.agent_mode}</Badge>
                <Badge variant="outline">
                  工具: {draft.tools_count} 个
                </Badge>
              </div>
              <div className="space-y-1">
                <Label>Max Tokens</Label>
                <Input
                  type="number"
                  min={1}
                  max={32768}
                  value={draft.max_tokens}
                  disabled={!isAdmin}
                  onChange={(event) => setDraft({ ...draft, max_tokens: Number(event.target.value) })}
                />
              </div>

              <div className="grid gap-4 md:grid-cols-3">
                {([
                  ["内置工具", "enabled_tools", draft.available_tools.map((name) => ({ name, label: name }))],
                  ["Skills", "enabled_skills", draft.available_skills.map((item) => ({ name: item.name, label: item.display_name }))],
                  ["MCP Servers", "mcp_servers", draft.available_mcp_servers.map((name) => ({ name, label: name }))],
                ] as const).map(([label, key, options]) => (
                  <div key={key} className="space-y-2 rounded-md border p-3">
                    <Label>{label}</Label>
                    {options.length === 0 ? (
                      <p className="text-xs text-muted-foreground">暂无可选项</p>
                    ) : options.map((option) => (
                      <label key={option.name} className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={draft[key].includes(option.name)}
                          disabled={!isAdmin}
                          onChange={() => toggleListValue(key, option.name)}
                        />
                        {option.label}
                      </label>
                    ))}
                  </div>
                ))}
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
