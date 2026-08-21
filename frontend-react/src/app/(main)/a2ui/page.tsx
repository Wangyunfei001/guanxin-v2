"use client"

import * as React from "react"
import { BracketsCurly, Eye, Layout, Sparkle } from "@phosphor-icons/react"
import { toast } from "sonner"
import { PageHeader, StatStrip } from "@/components/layout/page-header"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Label } from "@/components/ui/label"
import { A2UIRenderer } from "@/components/a2ui/A2UIRenderer"
import { a2uiApi } from "@/lib/api/a2ui"
import type { A2UISchema } from "@/types"

function getSampleSchema(type: string): A2UISchema {
  const samples: Record<string, A2UISchema> = {
    form_card: {
      component_type: "form_card",
      props: {
        title: "示例表单",
        fields: [
          { name: "username", label: "用户名", type: "input", required: true },
          { name: "role", label: "角色", type: "select", options: ["admin", "user"] },
          { name: "bio", label: "简介", type: "textarea" },
        ],
        submit_text: "提交",
      },
    },
    info_card: {
      component_type: "info_card",
      props: {
        title: "信息卡片",
        content: "这是一个示例信息卡片",
        items: [
          { label: "名称", value: "观心 v2" },
          { label: "版本", value: "0.1.0" },
        ],
      },
    },
    list_card: {
      component_type: "list_card",
      props: {
        title: "检索结果",
        columns: [
          { key: "content", label: "内容" },
          { key: "score", label: "相关度" },
        ],
        rows: [
          { content: "示例内容 1", score: "0.95" },
          { content: "示例内容 2", score: "0.82" },
        ],
        show_score: true,
      },
    },
    confirm_card: {
      component_type: "confirm_card",
      props: {
        title: "确认操作",
        message: "确定要执行此操作吗？",
        confirm_text: "确认",
        cancel_text: "取消",
        danger: false,
      },
    },
    chart_card: {
      component_type: "chart_card",
      props: {
        title: "数据图表",
        chart_type: "bar",
        labels: ["1月", "2月", "3月", "4月", "5月"],
        values: [30, 45, 28, 60, 52],
      },
    },
  }
  return samples[type] || samples.info_card
}

function getSampleData(name: string): any {
  switch (name) {
    case "kb_result":
      return [
        { content: "示例文档片段 1", filename: "doc1.txt", score: 0.92 },
        { content: "示例文档片段 2", filename: "doc2.txt", score: 0.75 },
      ]
    case "skill_result":
      return { skill_name: "data_analysis", result: { success: true, output: { mean: 3.0, max: 5 } } }
    case "confirm_action":
      return { title: "确认删除", message: "确定要删除此文档吗？", danger: true }
    case "data_analysis":
      return {
        title: "数据分析",
        stats: { count: 5, mean: 3, median: 3, max: 5, min: 1 },
        chart_data: { type: "bar", labels: ["A", "B", "C", "D", "E"], values: [10, 25, 15, 30, 20] },
      }
    case "error":
      return { title: "执行失败", message: "技能执行过程中发生错误" }
    default:
      return {}
  }
}

export default function A2UIPreviewPage() {
  const [catalog, setCatalog] = React.useState<any[]>([])
  const [templates, setTemplates] = React.useState<any[]>([])
  const [selectedType, setSelectedType] = React.useState("")
  const [currentSchema, setCurrentSchema] = React.useState<A2UISchema | null>(null)
  const [schemaJson, setSchemaJson] = React.useState("")

  React.useEffect(() => {
    const loadData = async () => {
      const [catRes, tplRes] = await Promise.all([
        a2uiApi.getCatalog(),
        a2uiApi.getTemplates(),
      ])
      if (catRes.code === 0) {
        setCatalog(catRes.data)
        if (catRes.data.length > 0) {
          const firstType = catRes.data[0].component_type
          setSelectedType(firstType)
          const sample = getSampleSchema(firstType)
          setCurrentSchema(sample)
          setSchemaJson(JSON.stringify(sample, null, 2))
        }
      }
      if (tplRes.code === 0) {
        setTemplates(tplRes.data)
      }
    }
    loadData()
  }, [])

  const onTypeChange = (type: string) => {
    setSelectedType(type)
    const sample = getSampleSchema(type)
    setCurrentSchema(sample)
    setSchemaJson(JSON.stringify(sample, null, 2))
  }

  const loadTemplate = async (name: string) => {
    const sampleData = getSampleData(name)
    try {
      const res = await a2uiApi.renderTemplate(name, sampleData)
      if (res.code === 0) {
        setCurrentSchema(res.data)
        setSchemaJson(JSON.stringify(res.data, null, 2))
      }
    } catch {
      toast.error("加载模板失败")
    }
  }

  const applyJson = () => {
    try {
      const parsed = JSON.parse(schemaJson)
      setCurrentSchema(parsed)
      toast.success("已应用")
    } catch {
      toast.error("JSON 格式错误")
    }
  }

  return (
    <div className="mx-auto w-full max-w-[1500px] space-y-6 p-4 sm:p-6 lg:p-8">
      <PageHeader
        eyebrow="GENERATIVE UI"
        title="A2UI 工作台"
        description="选择组件、编辑 Schema，并在真实主题环境中验证 Agent 生成的结构化界面。"
      />

      <StatStrip
        items={[
          { label: "组件类型", value: catalog.length, icon: Layout, tone: "accent" },
          { label: "预设模板", value: templates.length, icon: Sparkle },
          { label: "当前组件", value: selectedType || "—", icon: Eye },
          { label: "协议", value: "schema", icon: BracketsCurly },
        ]}
      />

      <div className="grid min-h-[660px] overflow-hidden rounded-[18px] border bg-card shadow-panel lg:grid-cols-[220px_minmax(360px,1fr)_300px] xl:grid-cols-[240px_minmax(420px,1fr)_340px]">
        <aside className="border-b bg-muted/20 lg:border-b-0 lg:border-r">
          <div className="border-b px-4 py-4">
            <p className="text-sm font-semibold">组件与模板</p>
            <p className="mt-1 text-[11px] text-muted-foreground">选择一个渲染起点</p>
          </div>
          <div className="space-y-6 p-3">
            <section>
              <p className="px-2 pb-2 text-[10px] font-medium tracking-[0.1em] text-muted-foreground">COMPONENTS</p>
              <RadioGroup value={selectedType} onValueChange={onTypeChange} className="space-y-1">
                {catalog.map((component) => (
                  <Label
                    key={component.component_type}
                    htmlFor={`type-${component.component_type}`}
                    className="flex cursor-pointer items-center gap-3 rounded-[10px] px-2.5 py-2.5 text-xs font-normal transition-colors hover:bg-muted data-[selected=true]:bg-primary/8"
                    data-selected={selectedType === component.component_type}
                  >
                    <RadioGroupItem value={component.component_type} id={`type-${component.component_type}`} />
                    <span className="min-w-0 flex-1 truncate">{component.display_name || component.component_type}</span>
                  </Label>
                ))}
                {catalog.length === 0 && <p className="px-2 py-4 text-xs text-muted-foreground">正在读取目录</p>}
              </RadioGroup>
            </section>

            <section>
              <p className="px-2 pb-2 text-[10px] font-medium tracking-[0.1em] text-muted-foreground">TEMPLATES</p>
              <div className="space-y-1">
                {templates.map((template) => (
                  <button
                    key={template.name}
                    className="w-full rounded-[10px] px-2.5 py-2.5 text-left transition-colors hover:bg-muted"
                    onClick={() => void loadTemplate(template.name)}
                  >
                    <span className="block truncate text-xs font-medium">{template.name}</span>
                    <span className="mt-0.5 line-clamp-2 text-[10px] leading-4 text-muted-foreground">{template.description}</span>
                  </button>
                ))}
                {templates.length === 0 && <p className="px-2 py-4 text-xs text-muted-foreground">正在读取模板</p>}
              </div>
            </section>
          </div>
        </aside>

        <main className="flex min-w-0 flex-col border-b lg:border-b-0 lg:border-r">
          <div className="flex h-[65px] items-center justify-between border-b px-5">
            <div>
              <p className="text-sm font-semibold">实时预览</p>
              <p className="mt-0.5 font-mono text-[10px] text-muted-foreground">{selectedType || "NO COMPONENT"}</p>
            </div>
            <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
              <span className="size-1.5 rounded-full bg-primary" />
              LIVE
            </div>
          </div>
          <div className="relative flex flex-1 items-start justify-center overflow-auto bg-[radial-gradient(circle_at_50%_0%,hsl(var(--primary)/0.07),transparent_42%)] p-5 sm:p-8">
            <div className="w-full max-w-2xl rounded-[16px] border border-dashed border-border/80 bg-background/80 p-4 shadow-panel backdrop-blur sm:p-6">
              {currentSchema ? (
                <A2UIRenderer schema={currentSchema} />
              ) : (
                <div className="flex min-h-80 flex-col items-center justify-center text-center">
                  <Eye size={28} className="text-muted-foreground/45" />
                  <p className="mt-3 text-sm font-medium">等待 Schema</p>
                  <p className="mt-1 text-xs text-muted-foreground">选择组件类型或模板开始预览</p>
                </div>
              )}
            </div>
          </div>
        </main>

        <aside className="flex min-w-0 flex-col bg-[#0d1311] text-[#edf4f1]">
          <div className="flex h-[65px] items-center justify-between border-b border-white/10 px-4">
            <div>
              <p className="text-sm font-semibold">Schema JSON</p>
              <p className="mt-0.5 text-[10px] text-[#9eada7]">UTF-8 · A2UI</p>
            </div>
            <BracketsCurly size={18} className="text-primary" />
          </div>
          <div className="flex flex-1 flex-col gap-3 p-3">
            <Textarea
              value={schemaJson}
              onChange={(event) => setSchemaJson(event.target.value)}
              spellCheck={false}
              className="min-h-[500px] flex-1 resize-none border-white/10 bg-black/15 font-mono text-[11px] leading-5 text-[#dbe7e2] focus-visible:border-primary/40"
            />
            <Button className="w-full" onClick={applyJson}>应用 Schema</Button>
          </div>
        </aside>
      </div>
    </div>
  )
}
