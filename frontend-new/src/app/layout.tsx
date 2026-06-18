import { motion, AnimatePresence } from "framer-motion"
import { Sidebar } from "@/components/layout/sidebar"
import { AuroraBg } from "@/components/shared/aurora-bg"
import { BackgroundBeams } from "@/components/shared/background-beams"
import { CyberGrid } from "@/components/shared/cyber-grid"
import { ParticleBg } from "@/components/shared/particle-bg"

interface LayoutProps {
  children: React.ReactNode
  currentPage: string
  onNavigate: (page: string) => void
}

export function Layout({ children, currentPage, onNavigate }: LayoutProps) {
  return (
    <div className="flex h-screen overflow-hidden">
      {/* Background layers - order matters for z-index */}
      <AuroraBg />
      <BackgroundBeams />
      <CyberGrid />
      <ParticleBg />

      {/* Sidebar */}
      <Sidebar currentPage={currentPage} onNavigate={onNavigate} />

      {/* Main content */}
      <main className="flex-1 overflow-y-auto relative z-10">
        <div className="container mx-auto px-4 py-6 max-w-6xl">
          <AnimatePresence mode="wait">
            <motion.div
              key={currentPage}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.2 }}
            >
              {children}
            </motion.div>
          </AnimatePresence>
        </div>
      </main>
    </div>
  )
}
