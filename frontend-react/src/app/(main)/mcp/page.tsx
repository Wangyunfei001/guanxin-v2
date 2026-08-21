"use client"

import {
  CheckCircle,
  CloudArrowUp,
  Plugs,
  Plus,
  ShieldCheck,
  TerminalWindow,
  Trash,
} from "@phosphor-icons/react"
import * as React from "react"
import { toast } from "sonner"

import { EmptyState, PageHeader, StatStrip } from "@/components/layout/page-header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { mcpApi } from "@/lib/api/mcp"
import { useAuthStore } from "@/lib/stores/auth"
import { useMcpStore } from "@/lib/stores/mcp"

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

  const availableTools = React.useMemo(
    () => mcpStore.connections.flatMap((connection) => connection.tools || []),
    [mcpStore.connections],
  )

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
      toast.success("MCP Server 已注册")
      mcpStore.loadServers()
      setAddModalVisible(false)
    } catch {
      toast.error("添加失败")
    }
  }

  const handleConnect = async (name: string) => {
    setConnecting(name)
    try {
      const response = await mcpStore.connectServer(name)
      if (response.code === 0 && response.data.status === "connected") {
        toast.success(`连接成功，发现 ${response.data.tools?.length || 0} 个工具`)
        mcpStore.loadConnections()
      } else toast.error(response.data?.error || "连接失败")
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
      toast.success("MCP Server 已删除")
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
      const connection = mcpStore.connections.find((item) =>
        item.tools?.some((tool) => tool.name === toolCall.tool_name),
      )
      const response = await mcpStore.callTool(
        connection?.server_name || toolCall.server_name,
        toolCall.tool_name,
        args,
      )
      if (response.code === 0) toast.success("工具调用完成")
      else toast.error(response.data?.error || "调用失败")
    } catch {
      toast.error("参数不是有效 JSON")
    }
    setCallToolVisible(false)
  }

  return (
    <div className="mx-auto w-full max-w-[1280px] space-y-6 p-4 sm:p-6 lg:p-8">
      <PageHeader
        eyebrow="CONNECTIONS"
        title="MCP 连接"
        description="把经过授权的外部能力连接到 Agent。注册与连接操作仅对管理员开放。"
        actions={
          isAdmin ? (
            <Button onClick={showAddModal}>
              <Plus size={16} weight="bold" />
              注册 Server
            </Button>
          ) : (
            <Badge variant="outline" className="h-8 gap-1.5 px-3 text-muted-foreground">
              <ShieldCheck size={14} />
              只读视图
            </Badge>
          )
        }
      />

      <StatStrip
        items={[
          { label: "已注册 Server", value: mcpStore.servers.length, icon: TerminalWindow },
          { label: "活跃连接", value: mcpStore.connections.length, icon: Plugs, tone: "accent" },
          { label: "已发现工具", value: availableTools.length, icon: CloudArrowUp },
          { label: "权限边界", value: isAdmin ? "管理员" : "只读", icon: ShieldCheck },
        ]}
      />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.5fr)_minmax(320px,0.75fr)]">
        <Card className="overflow-hidden">
          <CardHeader className="border-b">
            <CardTitle>Server 资源</CardTitle>
            <p className="text-xs text-muted-foreground">本租户可使用的 MCP 服务定义</p>
          </CardHeader>
          {mcpStore.servers.length === 0 && !mcpStore.loading ? (
            <EmptyState
              icon={TerminalWindow}
              title="还没有 MCP Server"
              description={isAdmin ? "注册一个本地 stdio Server，让 Agent 获得外部工具。" : "管理员尚未为当前租户注册 MCP Server。"}
              action={isAdmin ? <Button size="sm" onClick={showAddModal}>注册 Server</Button> : undefined}
            />
          ) : (
            <CardContent className="divide-y p-0">
              {mcpStore.servers.map((server) => {
                const connected = mcpStore.connections.some(
                  (connection) => connection.server_name === server.name && connection.status === "connected",
                )
                return (
                  <article key={server.name} className="flex flex-col gap-4 p-4 transition-colors hover:bg-muted/25 sm:flex-row sm:items-center sm:px-5">
                    <div className="flex size-11 shrink-0 items-center justify-center rounded-[13px] border bg-muted/35 font-mono text-sm font-semibold text-primary">
                      {server.name.slice(0, 2).toUpperCase()}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-sm font-semibold">{server.name}</h3>
                        <Badge
                          variant="outline"
                          className={connected ? "border-primary/15 bg-primary/10 text-primary" : "text-muted-foreground"}
                        >
                          {connected ? "已连接" : "未连接"}
                        </Badge>
                      </div>
                      <p className="mt-1 text-xs leading-5 text-muted-foreground">
                        {server.description || "暂无描述"}
                      </p>
                      <p className="mt-1 truncate font-mono text-[10px] text-muted-foreground">
                        {server.command} {server.args.join(" ")}
                      </p>
                    </div>
                    {isAdmin && (
                      <div className="flex shrink-0 gap-1.5">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => void handleConnect(server.name)}
                          disabled={connecting === server.name || connected}
                        >
                          <Plugs size={14} />
                          {connecting === server.name ? "连接中" : connected ? "已连接" : "连接"}
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="size-9 text-muted-foreground hover:text-destructive"
                          onClick={() => setDeleteTarget(server.name)}
                          aria-label={`删除 ${server.name}`}
                        >
                          <Trash size={15} />
                        </Button>
                      </div>
                    )}
                  </article>
                )
              })}
            </CardContent>
          )}
        </Card>

        <Card className="h-fit overflow-hidden">
          <CardHeader className="flex-row items-center justify-between border-b">
            <div>
              <CardTitle>运行连接</CardTitle>
              <p className="mt-1 text-xs text-muted-foreground">当前进程已连接的服务</p>
            </div>
            {mcpStore.connections.length > 0 && (
              <Button size="sm" variant="outline" onClick={openCallTool}>试调用</Button>
            )}
          </CardHeader>
          <CardContent className="p-0">
            {mcpStore.connections.length === 0 ? (
              <EmptyState icon={Plugs} title="暂无活跃连接" description="连接 Server 后，发现的工具会出现在这里。" className="min-h-48" />
            ) : (
              <div className="divide-y">
                {mcpStore.connections.map((connection) => (
                  <div key={connection.server_name} className="p-4">
                    <div className="flex items-center gap-2">
                      <CheckCircle size={17} weight="fill" className="text-primary" />
                      <span className="text-sm font-medium">{connection.server_name}</span>
                      <span className="ml-auto font-mono text-[10px] text-muted-foreground">
                        {connection.tools?.length || 0} TOOLS
                      </span>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {connection.tools?.map((tool) => (
                        <Badge key={tool.name} variant="outline" className="font-mono text-[10px]">
                          {tool.name}
                        </Badge>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Dialog open={addModalVisible} onOpenChange={setAddModalVisible}>
        <DialogContent>
          <DialogHeader><DialogTitle>注册 MCP Server</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label>名称</Label>
              <Input value={newServer.name} onChange={(event) => setNewServer((current) => ({ ...current, name: event.target.value }))} placeholder="weather" />
            </div>
            <div className="space-y-1.5">
              <Label>启动命令</Label>
              <Input value={newServer.command} onChange={(event) => setNewServer((current) => ({ ...current, command: event.target.value }))} placeholder="python" />
            </div>
            <div className="space-y-1.5">
              <Label>参数</Label>
              <Input value={newServer.argsStr} onChange={(event) => setNewServer((current) => ({ ...current, argsStr: event.target.value }))} placeholder="-m app.mcp.weather_server" />
              <p className="text-[11px] text-muted-foreground">多个参数使用空格分隔</p>
            </div>
            <div className="space-y-1.5">
              <Label>描述</Label>
              <Input value={newServer.description} onChange={(event) => setNewServer((current) => ({ ...current, description: event.target.value }))} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddModalVisible(false)}>取消</Button>
            <Button onClick={() => void handleAdd()}>注册</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={callToolVisible} onOpenChange={setCallToolVisible}>
        <DialogContent>
          <DialogHeader><DialogTitle>试调用 MCP 工具</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label>工具</Label>
              <Select value={toolCall.tool_name} onValueChange={(value) => setToolCall((current) => ({ ...current, tool_name: value }))}>
                <SelectTrigger><SelectValue placeholder="选择工具" /></SelectTrigger>
                <SelectContent>
                  {availableTools.map((tool) => (
                    <SelectItem key={tool.name} value={tool.name}>{tool.name} — {tool.description}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>参数 JSON</Label>
              <Textarea value={toolCall.argsStr} rows={5} onChange={(event) => setToolCall((current) => ({ ...current, argsStr: event.target.value }))} placeholder='{"city":"北京"}' className="font-mono text-xs" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCallToolVisible(false)}>取消</Button>
            <Button onClick={() => void handleCallTool()} disabled={!toolCall.tool_name}>调用</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>删除 MCP Server</DialogTitle></DialogHeader>
          <p className="text-sm leading-6 text-muted-foreground">Server「{deleteTarget}」将从当前租户配置中删除。</p>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>取消</Button>
            <Button variant="destructive" onClick={() => void handleDelete()}>确认删除</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
