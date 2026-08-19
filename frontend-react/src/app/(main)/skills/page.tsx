"use client"

import * as React from "react"
import { Zap, Play } from "lucide-react"
import { toast } from "sonner"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
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
    skill.params.forEach((p) => {
      if (p.default !== undefined) values[p.name] = p.default
      if (p.name === "data") values[p.name] = "[1, 2, 3, 4, 5]"
      if (p.name === "text") values[p.name] = ""
    })
    setParamValues(values)
  }

  const handleExecute = async () => {
    if (!executeTarget) return
    setExecuting(true)
    try {
      const params: Record<string, any> = {}
      for (const [k, v] of Object.entries(paramValues)) {
        if (typeof v === "string" && k === "data") {
          try {
            params[k] = JSON.parse(v)
          } catch {
            params[k] = v
          }
        } else {
          params[k] = v
        }
      }
      const res = await executeSkill(executeTarget.name, params)
      if (res.code === 0) {
        setResultText(JSON.stringify(res.data, null, 2))
        setResultVisible(true)
      } else {
        toast.error(res.message || "执行失败")
      }
    } catch {
      toast.error("执行失败")
    } finally {
      setExecuting(false)
    }
    setExecuteTarget(null)
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {skills.map((skill) => (
          <Card key={skill.name} className="flex flex-col">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Zap className="h-4 w-4 text-yellow-500" />
                  <CardTitle className="text-sm">{skill.display_name}</CardTitle>
                </div>
                <Badge variant="secondary" className="bg-blue-100 text-blue-700">
                  {skill.category}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="flex flex-1 flex-col">
              <p className="mb-2 text-sm text-muted-foreground">{skill.description}</p>
              {skill.tags && skill.tags.length > 0 && (
                <div className="mb-2 flex flex-wrap gap-1">
                  {skill.tags.map((tag) => (
                    <Badge key={tag} variant="outline" className="text-xs">
                      {tag}
                    </Badge>
                  ))}
                </div>
              )}
              <Separator className="my-2" />
              <Button
                className="mt-auto w-full"
                size="sm"
                onClick={() => showExecuteModal(skill)}
              >
                <Play className="h-4 w-4" />
                执行
              </Button>
            </CardContent>
          </Card>
        ))}
        {skills.length === 0 && !loading && (
          <div className="col-span-full py-8 text-center text-muted-foreground">
            暂无技能
          </div>
        )}
      </div>

      {/* Execute Dialog */}
      <Dialog open={!!executeTarget} onOpenChange={(open) => !open && setExecuteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              执行技能: {executeTarget?.display_name}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            {executeTarget?.params.map((param) => (
              <div key={param.name} className="space-y-1">
                <Label className="text-xs">
                  {param.label || param.name}
                </Label>
                {param.type === "string" && param.name === "text" && (
                  <Textarea
                    value={paramValues[param.name] || ""}
                    onChange={(e) =>
                      setParamValues((prev) => ({ ...prev, [param.name]: e.target.value }))
                    }
                    rows={4}
                    placeholder={param.description}
                  />
                )}
                {param.type === "string" && param.name !== "text" && (
                  <Input
                    value={paramValues[param.name] || ""}
                    onChange={(e) =>
                      setParamValues((prev) => ({ ...prev, [param.name]: e.target.value }))
                    }
                    placeholder={param.description}
                  />
                )}
                {param.type === "number" && (
                  <Input
                    type="number"
                    value={paramValues[param.name] ?? ""}
                    onChange={(e) =>
                      setParamValues((prev) => ({
                        ...prev,
                        [param.name]: parseFloat(e.target.value) || 0,
                      }))
                    }
                    placeholder={param.description}
                  />
                )}
                {param.type === "boolean" && (
                  <Switch
                    checked={!!paramValues[param.name]}
                    onCheckedChange={(checked) =>
                      setParamValues((prev) => ({ ...prev, [param.name]: checked }))
                    }
                  />
                )}
                {!["string", "number", "boolean"].includes(param.type) && (
                  <Input
                    value={paramValues[param.name] || ""}
                    onChange={(e) =>
                      setParamValues((prev) => ({ ...prev, [param.name]: e.target.value }))
                    }
                    placeholder={param.description}
                  />
                )}
                <p className="text-xs text-muted-foreground">{param.description}</p>
              </div>
            ))}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setExecuteTarget(null)}>
              取消
            </Button>
            <Button onClick={handleExecute} disabled={executing}>
              {executing ? "执行中..." : "执行"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Result Dialog */}
      <Dialog open={resultVisible} onOpenChange={setResultVisible}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>执行结果</DialogTitle>
          </DialogHeader>
          <pre className="max-h-96 overflow-auto rounded-md bg-gray-100 p-4 text-xs">
            {resultText}
          </pre>
        </DialogContent>
      </Dialog>
    </div>
  )
}
