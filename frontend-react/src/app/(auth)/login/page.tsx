"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import { toast } from "sonner"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { useAuthStore } from "@/lib/stores/auth"

const presetAccounts = [
  { label: "管理员: admin / admin123 (租户A)", username: "admin", password: "admin123" },
  { label: "普通用户: user / user123 (租户A)", username: "user", password: "user123" },
  { label: "Demo 用户: demo / demo123 (租户B)", username: "demo", password: "demo123" },
] as const

export default function LoginPage() {
  const router = useRouter()
  const login = useAuthStore((s) => s.login)
  const [loading, setLoading] = React.useState(false)
  const [username, setUsername] = React.useState("")
  const [password, setPassword] = React.useState("")

  const fillAccount = (u: string, p: string) => {
    setUsername(u)
    setPassword(p)
  }

  const handleLogin = async (event?: React.FormEvent<HTMLFormElement>) => {
    event?.preventDefault()
    if (!username || !password) {
      toast.error("请输入用户名和密码")
      return
    }
    setLoading(true)
    try {
      const res = await login(username, password)
      if (res.code === 0) {
        toast.success("登录成功")
        router.push("/chat")
      } else {
        toast.error(res.message || "登录失败")
      }
    } catch {
      toast.error("网络错误，请检查后端服务是否启动")
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card className="w-[400px] shadow-xl">
      <CardHeader>
        <CardTitle className="text-center text-xl">
          观心 v2 - AI Agent 全栈 Demo
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <form className="space-y-4" onSubmit={handleLogin}>
          <div className="space-y-2">
            <Label htmlFor="username">用户名</Label>
            <Input
              id="username"
              name="username"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="请输入用户名"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">密码</Label>
            <Input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="请输入密码"
            />
          </div>
          <Button type="submit" disabled={loading} className="w-full">
            {loading ? "登录中..." : "登录"}
          </Button>
        </form>

        <div className="flex items-center gap-2">
          <Separator className="flex-1" />
          <span className="text-xs text-muted-foreground">预设账号</span>
          <Separator className="flex-1" />
        </div>

        <div className="space-y-2">
          {presetAccounts.map((acc) => (
            <Button
              key={acc.username}
              type="button"
              variant="outline"
              className="w-full justify-start text-xs"
              onClick={() => fillAccount(acc.username, acc.password)}
            >
              {acc.label}
            </Button>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
