import { useState } from "react"
import { Layout } from "@/app/layout"
import { Routes } from "@/app/routes"
import { Providers } from "@/app/providers"
import { LandingPage } from "@/pages/landing"
import { useAppStore } from "@/stores/app"

function App() {
  const [showLanding, setShowLanding] = useState(true)
  const currentPage = useAppStore((s) => s.currentPage)
  const setCurrentPage = useAppStore((s) => s.setCurrentPage)

  return (
    <Providers>
      {showLanding && (
        <LandingPage onEnter={() => setShowLanding(false)} />
      )}
      <Layout currentPage={currentPage} onNavigate={setCurrentPage}>
        <Routes currentPage={currentPage} />
      </Layout>
    </Providers>
  )
}

export default App
