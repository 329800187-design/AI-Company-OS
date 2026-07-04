import { create } from "zustand"

interface AppState {
  currentPage: string
  sidebarCollapsed: boolean
  pendingMessage: string | null
  setCurrentPage: (page: string) => void
  toggleSidebar: () => void
  setSidebarCollapsed: (collapsed: boolean) => void
  setPendingMessage: (msg: string | null) => void
}

export const useAppStore = create<AppState>((set) => ({
  currentPage: "home",
  sidebarCollapsed: false,
  pendingMessage: null,
  setCurrentPage: (page) => set({ currentPage: page }),
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
  setPendingMessage: (msg) => set({ pendingMessage: msg }),
}))
