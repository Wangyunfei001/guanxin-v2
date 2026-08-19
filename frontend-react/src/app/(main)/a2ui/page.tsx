"use client"

import * as React from "react"
import { toast } from "sonner"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
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
    <div className="grid grid-cols-12 gap-4">
      {/* Left: Component type + Templates */}
      <div className="col-span-3 space-y-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">组件类型</CardTitle>
          </CardHeader>
          <CardContent>
            <RadioGroup value={selectedType} onValueChange={onTypeChange}>
              {catalog.map((c) => (
                <div key={c.component_type} className="flex items-center gap-2 py-1">
                  <RadioGroupItem value={c.component_type} id={`type-${c.component_type}`} />
                  <Label htmlFor={`type-${c.component_type}`} className="text-sm font-normal cursor-pointer">
                    {c.display_name || c.component_type}
                  </Label>
                </div>
              ))}
              {catalog.length === 0 && (
                <p className="text-sm text-muted-foreground">加载中...</p>
              )}
            </RadioGroup>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">预设模板</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1">
              {templates.map((tpl) => (
                <div
                  key={tpl.name}
                  className="cursor-pointer rounded-md border p-2 hover:bg-accent"
                  onClick={() => loadTemplate(tpl.name)}
                >
                  <div className="text-sm font-medium">{tpl.name}</div>
                  <div className="text-xs text-muted-foreground">{tpl.description}</div>
                </div>
              ))}
              {templates.length === 0 && (
                <p className="text-sm text-muted-foreground">加载中...</p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Center: Preview */}
      <div className="col-span-6">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">实时预览</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="min-h-[400px] rounded-md bg-gray-50 p-4">
              {currentSchema ? (
                <A2UIRenderer schema={currentSchema} />
              ) : (
                <div className="flex h-64 items-center justify-center text-muted-foreground">
                  选择组件类型或模板开始预览
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Right: JSON editor */}
      <div className="col-span-3">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Schema JSON</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <Textarea
              value={schemaJson}
              onChange={(e) => setSchemaJson(e.target.value)}
              rows={20}
              className="font-mono text-xs"
            />
            <Button className="w-full" onClick={applyJson}>
              应用
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
