"use client"

import {
  ArrowsClockwise,
  Brain,
  Check,
  Cpu,
  FloppyDisk,
  Plugs,
  ShieldCheck,
  Wrench,
} from "@phosphor-icons/react"
import * as React from "react"
import { toast } from "sonner"

import { PageHeader, StatStrip } from "@/components/layout/page-header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"
import { Textarea } from "@/components/ui/textarea"
import { useAgentStore } from "@/lib/stores/agent"
import { useAuthStore } from "@/lib/stores/auth"
import { cn } from "@/lib/utils"
import type { AgentConfig } from "@/types"

interface OptionListProps {
  label: string
  description: string
  options: { name: string; label: string }[]
  selected: string[]
  readOnly: boolean
  onToggle: (value: string) => void
}

function OptionList({ label, description, options, selected, readOnly, onToggle }: OptionListProps) {
  return (
    <section className="overflow-hidden rounded-[14px] border bg-card">
      <div className="border-b px-4 py-3">
        <p className="text-sm font-medium">{label}</p>
        <p className="mt-0.5 text-[11px] text-muted-foreground">{description}</p>
      </div>
      <div className="divide-y">
        {options.length === 0 ? (
          <p className="px-4 py-5 text-xs text-muted-foreground">暂无可选项</p>
        ) : (
          options.map((option) => {
            const active = selected.includes(option.name)
            return (
              <label
                key={option.name}
                className={cn(
                  "flex min-h-11 items-center gap-3 px-4 py-2.5 text-xs transition-colors",
                  readOnly ? "cursor-default" : "cursor-pointer hover:bg-muted/35",
                )}
              >
                <input
                  type="checkbox"
                  className="sr-only"
                  checked={active}
                  disabled={readOnly}
                  onChange={() => onToggle(option.name)}
                />
                <span
                  className={cn(
                    "flex size-4 items-center justify-center rounded-[5px] border",
                    active ? "border-primary bg-primary text-primary-foreground" : "border-border bg-background",
                  )}
                >
                  {active && <Check size={11} weight="bold" />}
                </span>
                <span className="min-w-0 flex-1 truncate">{option.label}</span>
              </label>
            )
          })
        )}
      </div>
    </section>
  )
}

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
    toast.success("已恢复服务器配置")
  }

  const handleSave = async () => {
    if (!draft) return
    await saveConfig(draft)
    toast.success("配置已保存，将在下一轮对话生效")
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

  return (
    <div className="mx-auto w-full max-w-[1280px] space-y-6 p-4 sm:p-6 lg:p-8">
      <PageHeader
        eyebrow="AGENT RUNTIME"
        title="Agent 配置"
        description="定义当前租户的模型、系统指令和能力边界。保存后的配置从下一轮对话开始生效。"
        actions={
          <>
            <Button variant="outline" onClick={handleRefresh}>
              <ArrowsClockwise size={16} />
              恢复服务器值
            </Button>
            {isAdmin && draft && (
              <Button disabled={saving} onClick={() => void handleSave()}>
                <FloppyDisk size={16} weight="bold" />
                {saving ? "保存中" : "保存配置"}
              </Button>
            )}
          </>
        }
      />

      <div className={cn(
        "flex items-start gap-3 rounded-[14px] border px-4 py-3",
        isAdmin ? "border-primary/20 bg-primary/[0.045]" : "bg-muted/35",
      )}>
        <ShieldCheck size={19} className={isAdmin ? "text-primary" : "text-muted-foreground"} />
        <div>
          <p className="text-sm font-medium">{isAdmin ? "管理员编辑模式" : "配置只读"}</p>
          <p className="mt-0.5 text-xs leading-5 text-muted-foreground">
            {isAdmin
              ? "你可以修改本租户配置；服务器会校验模型和所有能力名称。"
              : "当前账号可以读取并使用配置，但只有管理员能进行修改。"}
          </p>
        </div>
      </div>

      <StatStrip
        items={[
          { label: "当前模型", value: draft?.model || "—", icon: Cpu, tone: "accent" },
          { label: "已启用工具", value: draft?.enabled_tools.length || 0, icon: Wrench },
          { label: "已启用 Skills", value: draft?.enabled_skills.length || 0, icon: Brain },
          { label: "MCP Servers", value: draft?.mcp_servers.length || 0, icon: Plugs },
        ]}
      />

      {configLoading || !draft ? (
        <Card>
          <div className="flex min-h-72 items-center justify-center text-sm text-muted-foreground">正在读取 Agent 配置</div>
        </Card>
      ) : (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.75fr)]">
          <div className="space-y-6">
            <Card>
              <CardHeader className="border-b">
                <CardTitle>模型运行参数</CardTitle>
                <p className="text-xs text-muted-foreground">服务端白名单内的推理配置</p>
              </CardHeader>
              <CardContent className="space-y-5 pt-5">
                <div className="grid gap-5 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label htmlFor="agent-model">模型</Label>
                    <select
                      id="agent-model"
                      className="flex h-10 w-full rounded-[10px] border border-input bg-background px-3 text-sm outline-none focus:border-primary/55 focus:ring-2 focus:ring-primary/12 disabled:cursor-not-allowed disabled:opacity-60"
                      value={draft.model}
                      disabled={!isAdmin}
                      onChange={(event) => setDraft({ ...draft, model: event.target.value })}
                    >
                      {draft.available_models.map((model) => <option key={model} value={model}>{model}</option>)}
                    </select>
                    <p className="text-[11px] text-muted-foreground">仅显示服务端允许的模型</p>
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="max-tokens">Max Tokens</Label>
                    <Input
                      id="max-tokens"
                      type="number"
                      min={1}
                      max={32768}
                      value={draft.max_tokens}
                      disabled={!isAdmin}
                      onChange={(event) => setDraft({ ...draft, max_tokens: Number(event.target.value) })}
                    />
                    <p className="text-[11px] text-muted-foreground">允许范围 1–32768</p>
                  </div>
                </div>

                <div className="space-y-3 rounded-[12px] border bg-muted/20 p-4">
                  <div className="flex items-center justify-between">
                    <Label>Temperature</Label>
                    <span className="font-mono text-xs text-primary">{draft.temperature.toFixed(1)}</span>
                  </div>
                  <Slider
                    value={[draft.temperature]}
                    min={0}
                    max={2}
                    step={0.1}
                    disabled={!isAdmin}
                    onValueChange={([temperature]) => setDraft({ ...draft, temperature })}
                  />
                  <div className="flex justify-between text-[10px] text-muted-foreground">
                    <span>稳定 0</span><span>平衡 1</span><span>发散 2</span>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="system-prompt">系统提示词</Label>
                  <Textarea
                    id="system-prompt"
                    value={draft.system_prompt}
                    rows={11}
                    readOnly={!isAdmin}
                    onChange={(event) => setDraft({ ...draft, system_prompt: event.target.value })}
                    className="resize-none bg-muted/20 font-mono text-xs leading-6"
                  />
                </div>
              </CardContent>
            </Card>

            <div className="grid gap-4 md:grid-cols-3">
              <OptionList
                label="内置工具"
                description="Agent 原生能力"
                options={draft.available_tools.map((name) => ({ name, label: name }))}
                selected={draft.enabled_tools}
                readOnly={!isAdmin}
                onToggle={(value) => toggleListValue("enabled_tools", value)}
              />
              <OptionList
                label="Skills"
                description="确定性本地能力"
                options={draft.available_skills.map((item) => ({ name: item.name, label: item.display_name }))}
                selected={draft.enabled_skills}
                readOnly={!isAdmin}
                onToggle={(value) => toggleListValue("enabled_skills", value)}
              />
              <OptionList
                label="MCP Servers"
                description="已注册外部连接"
                options={draft.available_mcp_servers.map((name) => ({ name, label: name }))}
                selected={draft.mcp_servers}
                readOnly={!isAdmin}
                onToggle={(value) => toggleListValue("mcp_servers", value)}
              />
            </div>
          </div>

          <aside className="space-y-6">
            <Card>
              <CardHeader className="border-b">
                <CardTitle>运行环境</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4 pt-5">
                {[
                  ["Agent", draft.name],
                  ["模式", draft.agent_mode],
                  ["API Base", draft.api_base],
                  ["租户", draft.tenant_id],
                ].map(([label, value]) => (
                  <div key={label} className="grid grid-cols-[80px_minmax(0,1fr)] gap-3 border-b pb-3 last:border-0 last:pb-0">
                    <span className="text-xs text-muted-foreground">{label}</span>
                    <span className="break-all text-right font-mono text-[11px]">{value}</span>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card className="overflow-hidden">
              <CardHeader className="border-b">
                <CardTitle>可用 Skill 详情</CardTitle>
              </CardHeader>
              <CardContent className="divide-y p-0">
                {loading ? (
                  <p className="p-5 text-xs text-muted-foreground">正在同步</p>
                ) : skills.length === 0 ? (
                  <p className="p-5 text-xs text-muted-foreground">暂无可用 Skill</p>
                ) : (
                  skills.map((skill) => (
                    <div key={skill.name} className="p-4">
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-xs font-medium">{skill.display_name}</p>
                        <Badge variant="outline">{skill.category}</Badge>
                      </div>
                      <p className="mt-1.5 line-clamp-2 text-[11px] leading-5 text-muted-foreground">{skill.description}</p>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>
          </aside>
        </div>
      )}
    </div>
  )
}
