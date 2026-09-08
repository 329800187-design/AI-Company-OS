import { lazy, Suspense } from "react"
import { ErrorBoundary } from "@/components/error-boundary"

// Lazy load pages
const HomePage = lazy(() => import("@/pages/home"))
const BossPage = lazy(() => import("@/pages/boss"))
const MarketingPage = lazy(() => import("@/pages/marketing"))
const ImagePage = lazy(() => import("@/pages/image"))
const DataPage = lazy(() => import("@/pages/data"))
const ResearchPage = lazy(() => import("@/pages/research"))
const WebsitePage = lazy(() => import("@/pages/website"))
const SettingsPage = lazy(() => import("@/pages/settings"))
const DashboardPage = lazy(() => import("@/pages/dashboard"))
const TemplatesPage = lazy(() => import("@/pages/templates"))
const AgentConsolePage = lazy(() => import("@/pages/agent-console"))
const MissionsPage = lazy(() => import("@/pages/missions"))
const MemoryPage = lazy(() => import("@/pages/memory"))
const ReportsPage = lazy(() => import("@/pages/reports"))
const UsagePage = lazy(() => import("@/pages/usage"))
const SkillsPage = lazy(() => import("@/pages/skills"))
const GovernancePage = lazy(() => import("@/pages/governance"))
const DeliveryPage = lazy(() => import("@/pages/delivery"))

const Loading = () => (
  <div className="flex items-center justify-center h-64">
    <div className="flex flex-col items-center gap-4">
      <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      <p className="text-sm text-muted-foreground">加载中...</p>
    </div>
  </div>
)

interface RoutesProps {
  currentPage: string
}

export function Routes({ currentPage }: RoutesProps) {
  const renderPage = () => {
    switch (currentPage) {
      case "home":
        return <HomePage />
      case "boss":
        return <BossPage />
      case "marketing":
        return <MarketingPage />
      case "image":
        return <ImagePage />
      case "data":
        return <DataPage />
      case "research":
        return <ResearchPage />
      case "website":
        return <WebsitePage />
      case "settings":
        return <SettingsPage />
      case "dashboard":
        return <DashboardPage />
      case "templates":
        return <TemplatesPage />
      case "agent-console":
        return <AgentConsolePage />
      case "missions":
        return <MissionsPage />
      case "memory":
        return <MemoryPage />
      case "reports":
        return <ReportsPage />
      case "usage":
        return <UsagePage />
      case "skills":
        return <SkillsPage />
      case "governance":
        return <GovernancePage />
      case "delivery":
        return <DeliveryPage />
      default:
        return <HomePage />
    }
  }

  return (
    <ErrorBoundary>
      <Suspense fallback={<Loading />}>
        {renderPage()}
      </Suspense>
    </ErrorBoundary>
  )
}
