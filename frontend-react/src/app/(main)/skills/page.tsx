"use client"

import { BracketsCurly, CheckCircle, Lightning, Play, Stack } from "@phosphor-icons/react"
import * as React from "react"
import { toast } from "sonner"

import { EmptyState, PageHeader, StatStrip } from "@/components/layout/page-header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { useSkillStore } from "@/lib/stores/skill"
import type { SkillMetadata } from "@/types"

export default function SkillsPage() {
  const { skills, loading, loadSkills, executeSkill } = useSkillStore()
  const [executeTarget, setExecuteTarget] = React.useState<SkillMetadata | null>(null)
  const [paramValues, setParamValues] = React.useState<Record<string, any>>({})
  const [resultText, setResultText] = React.useState("")
  const [resultVisible, setResultVisible] = React.useState(false)
  const [executing, setExecuting] = React.useState(false)

  React.useEffect(() => {
    loadSkills()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const showExecuteModal = (skill: SkillMetadata) => {
    setExecuteTarget(skill)
    const values: Record<string, any> = {}
    skill.params.forEach((param) => {
      if (param.default !== undefined) values[param.name] = param.default
      if (param.name === "data") values[param.name] = "[1, 2, 3, 4, 5]"
      if (param.name === "text") values[param.name] = ""
    })
    setParamValues(values)
  }

  const handleExecute = async () => {
    if (!executeTarget) return
    setExecuting(true)
    try {
      const params: Record<string, any> = {}
      for (const [key, value] of Object.entries(paramValues)) {
        if (typeof value === "string" && key === "data") {
          try {
            params[key] = JSON.parse(value)
          } catch {
            params[key] = value
          }
        } else params[key] = value
      }
      const response = await executeSkill(executeTarget.name, params)
      if (response.code === 0) {
        setResultText(JSON.stringify(response.data, null, 2))
        setResultVisible(true)
      } else toast.error(response.message || "执行失败")
    } catch {
      toast.error("执行失败")
    } finally {
      setExecuting(false)
    }
    setExecuteTarget(null)
  }

  const categories = new Set(skills.map((skill) => skill.category)).size
  const paramsCount = skills.reduce((sum, skill) => sum + skill.params.length, 0)

  return (
    <div className="mx-auto w-full max-w-[1280px] space-y-6 p-4 sm:p-6 lg:p-8">
      <PageHeader
        eyebrow="CAPABILITIES"
        title="Skills"
        description="可组合的本地能力单元。每个 Skill 都有明确输入、输出和服务端权限边界。"
      />

      <StatStrip
        items={[
          { label: "可用 Skills", value: skills.length, icon: Lightning, tone: "accent" },
          { label: "能力分类", value: categories, icon: Stack },
          { label: "输入参数", value: paramsCount, icon: BracketsCurly },
          { label: "运行状态", value: loading ? "同步中" : "正常", icon: CheckCircle },
        ]}
      />

      <Card className="overflow-hidden">
        {skills.length === 0 && !loading ? (
          <EmptyState
            icon={Lightning}
            title="暂无可用 Skill"
            description="服务端还没有向当前用户开放可执行能力。"
          />
        ) : (
          <CardContent className="divide-y p-0">
            {skills.map((skill, index) => (
              <article
                key={skill.name}
                className="group grid gap-4 p-4 transition-colors hover:bg-muted/25 sm:grid-cols-[auto_minmax(0,1fr)_auto] sm:items-center sm:px-5"
              >
                <div className="flex size-11 items-center justify-center rounded-[13px] border bg-muted/35 text-primary">
                  <Lightning size={20} weight={index === 0 ? "fill" : "regular"} />
                </div>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-sm font-semibold">{skill.display_name}</h3>
                    <Badge variant="outline" className="text-muted-foreground">{skill.category}</Badge>
                    <Badge variant="outline" className="border-primary/15 bg-primary/8 text-primary">
                      {skill.status || "available"}
                    </Badge>
                  </div>
                  <p className="mt-1.5 max-w-3xl text-xs leading-5 text-muted-foreground">
                    {skill.description}
                  </p>
                  <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    <span className="mr-1 font-mono text-[10px] text-muted-foreground">{skill.name}</span>
                    {skill.tags?.map((tag) => (
                      <span key={tag} className="rounded-md bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
                <Button size="sm" variant="outline" onClick={() => showExecuteModal(skill)}>
                  <Play size={14} weight="fill" />
                  试运行
                </Button>
              </article>
            ))}
          </CardContent>
        )}
      </Card>

      <Dialog open={!!executeTarget} onOpenChange={(open) => !open && setExecuteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <p className="text-[11px] font-medium tracking-[0.1em] text-primary">SKILL RUNNER</p>
            <DialogTitle>{executeTarget?.display_name}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            {executeTarget?.params.map((param) => (
              <div key={param.name} className="space-y-1.5">
                <Label className="text-xs">{param.label || param.name}</Label>
                {param.type === "string" && param.name === "text" && (
                  <Textarea
                    value={paramValues[param.name] || ""}
                    onChange={(event) =>
                      setParamValues((current) => ({ ...current, [param.name]: event.target.value }))
                    }
                    rows={4}
                    placeholder={param.description}
                  />
                )}
                {param.type === "string" && param.name !== "text" && (
                  <Input
                    value={paramValues[param.name] || ""}
                    onChange={(event) =>
                      setParamValues((current) => ({ ...current, [param.name]: event.target.value }))
                    }
                    placeholder={param.description}
                  />
                )}
                {param.type === "number" && (
                  <Input
                    type="number"
                    value={paramValues[param.name] ?? ""}
                    onChange={(event) =>
                      setParamValues((current) => ({
                        ...current,
                        [param.name]: parseFloat(event.target.value) || 0,
                      }))
                    }
                    placeholder={param.description}
                  />
                )}
                {param.type === "boolean" && (
                  <Switch
                    checked={!!paramValues[param.name]}
                    onCheckedChange={(checked) =>
                      setParamValues((current) => ({ ...current, [param.name]: checked }))
                    }
                  />
                )}
                {!['string', 'number', 'boolean'].includes(param.type) && (
                  <Input
                    value={paramValues[param.name] || ""}
                    onChange={(event) =>
                      setParamValues((current) => ({ ...current, [param.name]: event.target.value }))
                    }
                    placeholder={param.description}
                  />
                )}
                <p className="text-[11px] leading-5 text-muted-foreground">{param.description}</p>
              </div>
            ))}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setExecuteTarget(null)}>取消</Button>
            <Button onClick={() => void handleExecute()} disabled={executing}>
              {executing ? "执行中" : "执行 Skill"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={resultVisible} onOpenChange={setResultVisible}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>执行结果</DialogTitle>
          </DialogHeader>
          <pre className="max-h-96 overflow-auto rounded-[12px] border bg-muted/45 p-4 font-mono text-xs leading-5">
            {resultText}
          </pre>
        </DialogContent>
      </Dialog>
    </div>
  )
}
