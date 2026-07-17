import { motion, AnimatePresence } from "framer-motion"
import { Sidebar } from "@/components/layout/sidebar"

interface LayoutProps {
  children: React.ReactNode
  currentPage: string
  onNavigate: (page: string) => void
}

export function Layout({ children, currentPage, onNavigate }: LayoutProps) {
  return (
    <div className="flex h-screen overflow-hidden bg-[#F4F3EF]">
      {/* Sidebar */}
      <Sidebar currentPage={currentPage} onNavigate={onNavigate} />

      {/* Main content */}
      <main className="flex-1 overflow-y-auto relative">
        <div className="container mx-auto px-4 py-6 max-w-6xl">
          <AnimatePresence mode="wait">
            <motion.div
              key={currentPage}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.3, ease: [0.23, 1, 0.32, 1] }}
            >
              {children}
            </motion.div>
          </AnimatePresence>
        </div>
      </main>
    </div>
  )
}
