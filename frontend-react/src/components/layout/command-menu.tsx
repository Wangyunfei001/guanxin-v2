"use client"

import { ArrowRight, MagnifyingGlass } from "@phosphor-icons/react"
import { useRouter } from "next/navigation"
import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandShortcut,
} from "@/components/ui/command"
import { navigationGroups } from "./navigation-items"

export function CommandMenu() {
  const router = useRouter()
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault()
        setOpen((current) => !current)
      }
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [])

  const go = (href: string) => {
    setOpen(false)
    router.push(href)
  }

  return (
    <>
      <Button
        variant="outline"
        className="hidden h-9 w-64 justify-between border-border/70 bg-background/70 px-3 text-muted-foreground shadow-none lg:flex"
        onClick={() => setOpen(true)}
      >
        <span className="flex items-center gap-2">
          <MagnifyingGlass size={16} />
          搜索页面与操作
        </span>
        <kbd className="rounded border bg-muted px-1.5 py-0.5 font-mono text-[10px]">⌘K</kbd>
      </Button>
      <Button
        variant="ghost"
        size="icon"
        className="size-9 lg:hidden"
        onClick={() => setOpen(true)}
        aria-label="打开命令搜索"
      >
        <MagnifyingGlass size={18} />
      </Button>
      <CommandDialog open={open} onOpenChange={setOpen}>
        <CommandInput placeholder="搜索页面与操作" />
        <CommandList>
          <CommandEmpty>没有匹配结果</CommandEmpty>
          {navigationGroups.map((group) => (
            <CommandGroup key={group.label} heading={group.label}>
              {group.items.map((item) => {
                const Icon = item.icon
                return (
                  <CommandItem key={item.href} onSelect={() => go(item.href)}>
                    <Icon size={18} />
                    <span>{item.label}</span>
                    <CommandShortcut>
                      <ArrowRight size={14} />
                    </CommandShortcut>
                  </CommandItem>
                )
              })}
            </CommandGroup>
          ))}
        </CommandList>
      </CommandDialog>
    </>
  )
}
