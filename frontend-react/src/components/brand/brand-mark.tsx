import { cn } from "@/lib/utils"

interface BrandMarkProps {
  className?: string
  showWordmark?: boolean
}

export function BrandMark({ className, showWordmark = false }: BrandMarkProps) {
  return (
    <div className={cn("inline-flex items-center gap-3", className)}>
      <svg
        viewBox="0 0 40 40"
        className="size-9 shrink-0"
        fill="none"
        role="img"
        aria-label="观心"
      >
        <path
          d="M31.8 11.5C28.7 7.9 24.2 5.6 19.2 5.6 10.6 5.6 3.6 12.2 3.6 20.4s7 14.8 15.6 14.8c4.8 0 9.2-2.1 12.3-5.5"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
        />
        <path
          d="M28.2 14.6c-2.1-2.5-5.3-4-8.8-4-5.6 0-10.2 4.3-10.2 9.8s4.6 9.8 10.2 9.8c3.4 0 6.4-1.6 8.5-3.9"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
          opacity="0.72"
        />
        <circle cx="19.5" cy="20.4" r="3.2" fill="currentColor" />
      </svg>
      {showWordmark && (
        <span className="text-[15px] font-semibold tracking-[-0.02em]">观心 v2</span>
      )}
    </div>
  )
}
