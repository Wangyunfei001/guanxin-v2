import { AuthGuard } from "@/components/auth/AuthGuard"
import { SideNav } from "@/components/layout/SideNav"
import { Header } from "@/components/layout/Header"

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
      <div className="flex h-screen overflow-hidden">
        <SideNav />
        <div className="flex flex-1 flex-col overflow-hidden">
          <Header />
          <main className="flex-1 overflow-auto bg-gray-50 p-2 md:p-6">
            <div className="mx-auto max-w-7xl rounded-lg bg-white p-2 shadow-sm min-h-[calc(100vh-96px)] md:p-6 md:min-h-[calc(100vh-160px)]">
              {children}
            </div>
          </main>
        </div>
      </div>
    </AuthGuard>
  )
}
