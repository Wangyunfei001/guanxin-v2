"use client"

import { ArrowRight, Database, Path, ShieldCheck, UserCircle } from "@phosphor-icons/react"
import { motion, useReducedMotion } from "motion/react"
import { useRouter } from "next/navigation"
import * as React from "react"
import { toast } from "sonner"

import { BrandMark } from "@/components/brand/brand-mark"
import { ThemeToggle } from "@/components/theme/theme-toggle"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useAuthStore } from "@/lib/stores/auth"

const presetAccounts = [
  { role: "管理员", tenant: "租户 A", username: "admin", password: "admin123" },
  { role: "普通用户", tenant: "租户 A", username: "user", password: "user123" },
  { role: "Demo 用户", tenant: "租户 B", username: "demo", password: "demo123" },
] as const

const capabilities = [
  { icon: Database, title: "知识可追溯", description: "本地向量检索与来源呈现" },
  { icon: Path, title: "过程可介入", description: "多步骤工作流与审批状态恢复" },
  { icon: ShieldCheck, title: "边界可验证", description: "租户隔离与服务端权限校验" },
]

export default function LoginPage() {
  const router = useRouter()
  const reduceMotion = useReducedMotion()
  const login = useAuthStore((state) => state.login)
  const [loading, setLoading] = React.useState(false)
  const [username, setUsername] = React.useState("")
  const [password, setPassword] = React.useState("")

  const fillAccount = (nextUsername: string, nextPassword: string) => {
    setUsername(nextUsername)
    setPassword(nextPassword)
  }

  const handleLogin = async (event?: React.FormEvent<HTMLFormElement>) => {
    event?.preventDefault()
    if (!username || !password) {
      toast.error("请输入用户名和密码")
      return
    }
    setLoading(true)
    try {
      const response = await login(username, password)
      if (response.code === 0) {
        toast.success("欢迎回来")
        router.push("/assistant")
      } else toast.error(response.message || "登录失败")
    } catch {
      toast.error("无法连接服务，请检查后端是否已启动")
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="relative grid min-h-[100dvh] overflow-hidden lg:grid-cols-[minmax(0,1.12fr)_minmax(440px,0.88fr)]">
      <div className="absolute right-4 top-4 z-20 lg:right-6 lg:top-6">
        <ThemeToggle />
      </div>

      <section className="relative hidden overflow-hidden border-r bg-[#0b0f0e] p-10 text-[#edf4f1] lg:flex lg:flex-col lg:justify-between xl:p-14">
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute -left-40 -top-44 size-[620px] rounded-full border border-primary/15" />
          <div className="absolute -left-16 -top-20 size-[420px] rounded-full border border-primary/10" />
          <div className="absolute bottom-[-220px] right-[-120px] size-[520px] rounded-full bg-primary/[0.055] blur-3xl" />
          <div className="absolute inset-0 opacity-[0.035] [background-image:linear-gradient(to_right,#fff_1px,transparent_1px),linear-gradient(to_bottom,#fff_1px,transparent_1px)] [background-size:44px_44px]" />
        </div>

        <div className="relative z-10">
          <BrandMark showWordmark className="text-primary" />
        </div>

        <div className="relative z-10 max-w-2xl pb-8">
          <motion.div
            className="relative mb-10 flex size-24 items-center justify-center"
            initial={reduceMotion ? false : { opacity: 0, scale: 0.92 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: reduceMotion ? 0 : 0.7, ease: [0.16, 1, 0.3, 1] }}
          >
            <motion.div
              className="absolute inset-0 rounded-[30px] border border-primary/25"
              animate={reduceMotion ? undefined : { rotate: [0, 4, 0] }}
              transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
            />
            <div className="absolute inset-3 rounded-[23px] border border-primary/15 bg-primary/[0.055]" />
            <BrandMark className="scale-[1.45] text-primary" />
          </motion.div>

          <p className="text-[11px] font-medium tracking-[0.18em] text-primary">OBSERVABLE AI WORKSPACE</p>
          <h1 className="mt-5 max-w-xl text-[44px] font-semibold leading-[1.08] tracking-[-0.055em] xl:text-[54px]">
            理解意图，
            <br />
            也看见过程。
          </h1>
          <p className="mt-6 max-w-lg text-sm leading-7 text-[#9eada7]">
            观心把知识、工具和工作流编排成可观察的执行空间，让每一次回答都保留依据与边界。
          </p>
        </div>

        <div className="relative z-10 grid grid-cols-3 gap-5 border-t border-white/10 pt-6">
          {capabilities.map(({ icon: CapabilityIcon, title, description }) => (
            <div key={title}>
              <CapabilityIcon size={18} className="text-primary" />
              <p className="mt-3 text-xs font-medium">{title}</p>
              <p className="mt-1 text-[10px] leading-4 text-[#718078]">{description}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="relative flex items-center justify-center px-5 py-20 sm:px-10 lg:px-14">
        <div className="absolute inset-x-0 top-0 h-72 bg-[radial-gradient(circle_at_50%_0%,hsl(var(--primary)/0.09),transparent_65%)] lg:hidden" />
        <motion.div
          className="relative z-10 w-full max-w-[420px]"
          initial={reduceMotion ? false : { opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: reduceMotion ? 0 : 0.55, delay: 0.08, ease: [0.16, 1, 0.3, 1] }}
        >
          <div className="mb-10 lg:hidden">
            <BrandMark showWordmark className="text-primary" />
          </div>

          <p className="text-[11px] font-medium tracking-[0.14em] text-primary">WELCOME BACK</p>
          <h2 className="mt-3 text-[30px] font-semibold tracking-[-0.045em]">进入观心</h2>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">使用租户账号继续你的执行空间。</p>

          <form className="mt-8 space-y-5" onSubmit={handleLogin}>
            <div className="space-y-2">
              <Label htmlFor="username">用户名</Label>
              <Input
                id="username"
                name="username"
                autoComplete="username"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                placeholder="输入用户名"
                className="h-12"
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
                onChange={(event) => setPassword(event.target.value)}
                placeholder="输入密码"
                className="h-12"
              />
            </div>
            <Button type="submit" disabled={loading} className="h-12 w-full justify-between px-4">
              <span>{loading ? "正在验证" : "进入工作空间"}</span>
              <ArrowRight size={17} weight="bold" />
            </Button>
          </form>

          <div className="mt-8 border-t pt-6">
            <div className="flex items-center justify-between">
              <p className="text-xs font-medium">演示账号</p>
              <p className="text-[10px] text-muted-foreground">点击自动填充</p>
            </div>
            <div className="mt-3 space-y-2">
              {presetAccounts.map((account) => (
                <button
                  key={account.username}
                  type="button"
                  className="group flex w-full items-center gap-3 rounded-[12px] border border-border/75 px-3 py-2.5 text-left transition-colors hover:border-primary/25 hover:bg-primary/[0.035]"
                  onClick={() => fillAccount(account.username, account.password)}
                >
                  <div className="flex size-8 items-center justify-center rounded-[9px] bg-muted text-muted-foreground group-hover:text-primary">
                    <UserCircle size={17} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium">{account.role}</p>
                    <p className="mt-0.5 font-mono text-[10px] text-muted-foreground">{account.username} / {account.password}</p>
                  </div>
                  <span className="text-[10px] text-muted-foreground">{account.tenant}</span>
                </button>
              ))}
            </div>
          </div>
        </motion.div>
      </section>
    </main>
  )
}
