"use client"

import * as React from "react"
import { Plus, Plug, Trash2, Play, Server } from "lucide-react"
import { toast } from "sonner"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { useMcpStore } from "@/lib/stores/mcp"
import { mcpApi } from "@/lib/api/mcp"
import { useAuthStore } from "@/lib/stores/auth"

export default function McpPage() {
  const mcpStore = useMcpStore()
  const isAdmin = useAuthStore((state) => state.isAdmin)
  const [connecting, setConnecting] = React.useState("")
  const [addModalVisible, setAddModalVisible] = React.useState(false)
  const [callToolVisible, setCallToolVisible] = React.useState(false)
  const [deleteTarget, setDeleteTarget] = React.useState<string | null>(null)

  const [newServer, setNewServer] = React.useState({
    name: "",
    command: "python",
    argsStr: "",
    description: "",
  })

  const [toolCall, setToolCall] = React.useState({
    server_name: "",
    tool_name: "",
    argsStr: "{}",
  })

  const availableTools = React.useMemo(() => {
    const tools: any[] = []
    mcpStore.connections.forEach((c: any) => {
      if (c.tools) tools.push(...c.tools)
    })
    return tools
  }, [mcpStore.connections])

  React.useEffect(() => {
    mcpStore.loadServers()
    mcpStore.loadConnections()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const showAddModal = () => {
    setNewServer({ name: "", command: "python", argsStr: "", description: "" })
    setAddModalVisible(true)
  }

  const handleAdd = async () => {
    if (!newServer.name || !newServer.command) {
      toast.error("请填写名称和命令")
      return
    }
    try {
      await mcpApi.registerServer({
        name: newServer.name,
        command: newServer.command,
        args: newServer.argsStr.split(" ").filter(Boolean),
        description: newServer.description,
      })
      toast.success("添加成功")
      mcpStore.loadServers()
      setAddModalVisible(false)
    } catch {
      toast.error("添加失败")
    }
  }

  const handleConnect = async (name: string) => {
    setConnecting(name)
    try {
      const res = await mcpStore.connectServer(name)
      if (res.code === 0 && res.data.status === "connected") {
        toast.success(`连接成功，发现 ${res.data.tools?.length || 0} 个工具`)
        mcpStore.loadConnections()
      } else {
        toast.error(res.data?.error || "连接失败")
      }
    } catch {
      toast.error("连接失败")
    } finally {
      setConnecting("")
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    try {
      await mcpApi.unregisterServer(deleteTarget)
      toast.success("删除成功")
      mcpStore.loadServers()
    } catch {
      toast.error("删除失败")
    }
    setDeleteTarget(null)
  }

  const openCallTool = () => {
    setToolCall({
      server_name: mcpStore.connections[0]?.server_name || "",
      tool_name: "",
      argsStr: "{}",
    })
    setCallToolVisible(true)
  }

  const handleCallTool = async () => {
    try {
      const args = JSON.parse(toolCall.argsStr)
      const conn = mcpStore.connections.find((c: any) =>
        c.tools?.some((t: any) => t.name === toolCall.tool_name),
      )
      const serverName = conn?.server_name || ""
      const res = await mcpStore.callTool(serverName, toolCall.tool_name, args)
      if (res.code === 0) {
        toast.success("调用成功")
      } else {
        toast.error(res.data?.error || "调用失败")
      }
    } catch {
      toast.error("参数解析失败")
    }
    setCallToolVisible(false)
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        {/* Left: Server list */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm">MCP Server 配置</CardTitle>
              {isAdmin && (
                <Button size="sm" onClick={showAddModal}>
                  <Plus className="h-4 w-4" />
                  添加
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {mcpStore.servers.map((server) => (
                <div
                  key={server.name}
                  className="flex items-center gap-3 rounded-md border p-3"
                >
                  <Avatar className="h-8 w-8">
                    <AvatarFallback className="bg-cyan-500 text-xs text-white">
                      {server.name[0]?.toUpperCase()}
                    </AvatarFallback>
                  </Avatar>
                  <div className="flex-1">
                    <div className="text-sm font-medium">{server.name}</div>
                    <div className="text-xs text-muted-foreground">{server.description}</div>
                  </div>
                  {isAdmin && <div className="flex gap-1">
                    <Button
                      variant="link"
                      size="sm"
                      className="text-xs"
                      onClick={() => handleConnect(server.name)}
                      disabled={connecting === server.name}
                    >
                      <Plug className="h-3 w-3" />
                      {connecting === server.name ? "连接中..." : "连接"}
                    </Button>
                    <Button
                      variant="link"
                      size="sm"
                      className="text-xs text-red-500"
                      onClick={() => setDeleteTarget(server.name)}
                    >
                      <Trash2 className="h-3 w-3" />
                      删除
                    </Button>
                  </div>}
                </div>
              ))}
              {mcpStore.servers.length === 0 && !mcpStore.loading && (
                <div className="py-4 text-center text-sm text-muted-foreground">
                  暂无 MCP Server
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Right: Active connections */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">活跃连接</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {mcpStore.connections.map((conn: any, idx: number) => (
                <div key={idx} className="rounded-md border p-3">
                  <div className="mb-1 flex items-center gap-2">
                    <Badge variant="secondary" className="bg-green-100 text-green-700">
                      <Server className="mr-1 h-3 w-3" />
                      {conn.status}
                    </Badge>
                    <span className="text-sm font-medium">{conn.server_name}</span>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    工具: {conn.tools?.map((t: any) => t.name).join(", ") || "无"}
                  </div>
                </div>
              ))}
              {mcpStore.connections.length === 0 && (
                <div className="py-4 text-center text-sm text-muted-foreground">
                  暂无活跃连接
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {mcpStore.connections.length > 0 && (
        <Button onClick={openCallTool}>
          <Play className="h-4 w-4" />
          调用工具
        </Button>
      )}

      {/* Add Server Dialog */}
      <Dialog open={addModalVisible} onOpenChange={setAddModalVisible}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>添加 MCP Server</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1">
              <Label>名称</Label>
              <Input
                value={newServer.name}
                onChange={(e) => setNewServer((p) => ({ ...p, name: e.target.value }))}
              />
            </div>
            <div className="space-y-1">
              <Label>命令</Label>
              <Input
                value={newServer.command}
                onChange={(e) => setNewServer((p) => ({ ...p, command: e.target.value }))}
                placeholder="python"
              />
            </div>
            <div className="space-y-1">
              <Label>参数（空格分隔）</Label>
              <Input
                value={newServer.argsStr}
                onChange={(e) => setNewServer((p) => ({ ...p, argsStr: e.target.value }))}
                placeholder="-m app.mcp.weather_server"
              />
            </div>
            <div className="space-y-1">
              <Label>描述</Label>
              <Input
                value={newServer.description}
                onChange={(e) => setNewServer((p) => ({ ...p, description: e.target.value }))}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddModalVisible(false)}>
              取消
            </Button>
            <Button onClick={handleAdd}>添加</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Call Tool Dialog */}
      <Dialog open={callToolVisible} onOpenChange={setCallToolVisible}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>调用工具</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1">
              <Label>工具名称</Label>
              <Select
                value={toolCall.tool_name}
                onValueChange={(value) => setToolCall((p) => ({ ...p, tool_name: value }))}
              >
                <SelectTrigger>
                  <SelectValue placeholder="选择工具..." />
                </SelectTrigger>
                <SelectContent>
                  {availableTools.map((tool) => (
                    <SelectItem key={tool.name} value={tool.name}>
                      {tool.name} - {tool.description}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label>参数 (JSON)</Label>
              <Textarea
                value={toolCall.argsStr}
                rows={4}
                onChange={(e) => setToolCall((p) => ({ ...p, argsStr: e.target.value }))}
                placeholder='{"city": "北京"}'
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCallToolVisible(false)}>
              取消
            </Button>
            <Button onClick={handleCallTool}>调用</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确定删除？</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            MCP Server「{deleteTarget}」将被删除。
          </p>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              取消
            </Button>
            <Button variant="destructive" onClick={handleDelete}>
              删除
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
