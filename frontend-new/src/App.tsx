import { useState, useEffect, useCallback } from "react"
import { Layout } from "@/app/layout"
import { Routes } from "@/app/routes"
import { Providers } from "@/app/providers"
import { LandingPage } from "@/pages/landing"
import { useAppStore } from "@/stores/app"
import { ErrorBoundary } from "@/components/error-boundary"

function App() {
  const currentPage = useAppStore((s) => s.currentPage)
  const setCurrentPage = useAppStore((s) => s.setCurrentPage)

  // Determine initial page from URL: ?page=governance or #governance
  const [initialPage] = useState(() => {
    const params = new URLSearchParams(window.location.search)
    const pageParam = params.get("page")
    if (pageParam) return pageParam
    const hash = window.location.hash.replace("#", "")
    if (hash) return hash
    return null
  })

  const skipLanding = initialPage !== null
  const [showLanding, setShowLanding] = useState(!skipLanding)

  const handleEnter = useCallback(() => {
    setShowLanding(false)
  }, [])

  // If URL targets a specific page, set it and skip landing
  useEffect(() => {
    if (!initialPage) return

    const timeoutId = window.setTimeout(() => {
      setCurrentPage(initialPage)
      setShowLanding(false)
    }, 0)

    return () => window.clearTimeout(timeoutId)
  }, [initialPage, setCurrentPage])

  // Enter key shortcut on landing
  useEffect(() => {
    if (!showLanding) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Enter") handleEnter()
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [showLanding, handleEnter])

  return (
    <Providers>
      {showLanding && <LandingPage onEnter={handleEnter} />}
      <Layout currentPage={currentPage} onNavigate={setCurrentPage}>
        <ErrorBoundary>
          <Routes currentPage={currentPage} />
        </ErrorBoundary>
      </Layout>
    </Providers>
  )
}

export default App
