import { AuthGuard } from "@/components/auth/AuthGuard"
import { AppShell } from "@/components/layout/app-shell"

/**
 * Main application layout.
 * Wraps content with AuthGuard + SideNav + Header.
 */
export default function MainLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <AuthGuard>
      <AppShell>{children}</AppShell>
    </AuthGuard>
  )
}
