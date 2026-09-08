import { useState, type ElementType } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Home,
  Briefcase,
  FileText,
  Image,
  BarChart3,
  Search,
  Globe,
  Settings,
  ChevronDown,
  Activity,
  Menu,
  X,
  Zap,
  Cpu,
  PenTool,
  BookOpen,
  ClipboardList,
  Coins,
  Puzzle,
  Shield,
  Package,
} from "lucide-react"
import { cn } from "@/lib/utils"

interface SidebarProps {
  currentPage: string
  onNavigate: (page: string) => void
}

interface NavigationItem {
  id: string
  label: string
  icon: ElementType
  legacy?: boolean
}

interface NavItemProps {
  item: NavigationItem
  isActive: boolean
  collapsed: boolean
  onNavigate: (page: string) => void
  onCloseMobile: () => void
}

const navItems = [
  { id: "home", label: "首页", icon: Home },
  { id: "boss", label: "老板指挥台", icon: Briefcase, legacy: true },
]

const featureItems = [
  { id: "marketing", label: "写文案", icon: FileText },
  { id: "image", label: "做图片", icon: Image },
  { id: "data", label: "看数据", icon: BarChart3 },
  { id: "research", label: "做调研", icon: Search },
  { id: "website", label: "建网站", icon: Globe },
  { id: "templates", label: "场景模板", icon: PenTool },
  { id: "delivery", label: "交付中心", icon: Package },
]

const advancedItems = [
  { id: "missions", label: "任务中心", icon: Briefcase, legacy: true },
  { id: "reports", label: "报告中心", icon: ClipboardList },
  { id: "memory", label: "知识库", icon: BookOpen },
  { id: "skills", label: "技能库", icon: Puzzle },
  { id: "governance", label: "Governance", icon: Shield },
  { id: "usage", label: "用量统计", icon: Coins },
  { id: "agent-console", label: "Agent 控制台", icon: Cpu },
  { id: "dashboard", label: "系统状态", icon: Activity },
]

function NavItem({ item, isActive, collapsed, onNavigate, onCloseMobile }: NavItemProps) {
  return (
    <motion.button
      whileHover={{ x: 3 }}
      whileTap={{ scale: 0.98 }}
      onClick={() => {
        onNavigate(item.id)
        onCloseMobile()
      }}
      className={cn(
        "flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm transition-colors duration-200 relative",
        isActive
          ? "text-white bg-white/10"
          : "text-[#8A8A8A] hover:text-white hover:bg-white/5"
      )}
    >
      {isActive && (
        <motion.div
          layoutId="activeTab"
          className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 bg-white rounded-r-full"
        />
      )}

      <item.icon className="w-4 h-4 flex-shrink-0" />
      {!collapsed && (
        <>
          <span>{item.label}</span>
          {item.legacy && (
            <span className="ml-auto text-[9px] px-1.5 py-0.5 rounded bg-[#333] text-[#666]">
              旧版
            </span>
          )}
        </>
      )}
    </motion.button>
  )
}

export function Sidebar({ currentPage, onNavigate }: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)

  const sidebarContent = (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className="p-4 border-b border-border">
        <div className="flex items-center gap-3">
          <div
            className="w-9 h-9 rounded-xl bg-white flex items-center justify-center"
          >
            <Zap className="w-4 h-4 text-[#0B0B0B]" />
          </div>
          {!collapsed && (
            <div>
              <h1 className="text-base font-bold text-white">
                AI Company
              </h1>
              <p className="text-[10px] text-[#8A8A8A]">你的 AI 助手</p>
            </div>
          )}
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto p-3 space-y-1">
        {/* Main nav */}
        <div className="mb-2">
          {navItems.map((item) => (
            <NavItem
              key={item.id}
              item={item}
              isActive={currentPage === item.id}
              collapsed={collapsed}
              onNavigate={onNavigate}
              onCloseMobile={() => setMobileOpen(false)}
            />
          ))}
        </div>

        {/* Features */}
        <div className="border-t border-[#333333] pt-2 mt-2">
          {!collapsed && (
            <div className="px-3 py-1 text-[10px] text-[#666666] uppercase tracking-wider">
              常用功能
            </div>
          )}
          {featureItems.map((item) => (
            <NavItem
              key={item.id}
              item={item}
              isActive={currentPage === item.id}
              collapsed={collapsed}
              onNavigate={onNavigate}
              onCloseMobile={() => setMobileOpen(false)}
            />
          ))}
        </div>

        {/* Advanced */}
        <div className="border-t border-[#333333] pt-2 mt-2">
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center gap-2 px-3 py-1 text-[10px] text-[#666666] uppercase tracking-wider w-full hover:text-white"
          >
            {!collapsed && (
              <>
                更多功能
                <ChevronDown
                  className={cn(
                    "w-3 h-3 ml-auto transition-transform",
                    showAdvanced && "rotate-180"
                  )}
                />
              </>
            )}
          </button>
          <AnimatePresence>
            {showAdvanced && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="overflow-hidden mt-1 space-y-1"
              >
                {advancedItems.map((item) => (
                  <NavItem
                    key={item.id}
                    item={item}
                    isActive={currentPage === item.id}
                    collapsed={collapsed}
                    onNavigate={onNavigate}
                    onCloseMobile={() => setMobileOpen(false)}
                  />
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </nav>

      {/* Bottom */}
      <div className="p-3 border-t border-border">
        <NavItem
          item={{ id: "settings", label: "设置", icon: Settings }}
          isActive={currentPage === "settings"}
          collapsed={collapsed}
          onNavigate={onNavigate}
          onCloseMobile={() => setMobileOpen(false)}
        />
      </div>
    </div>
  )

  return (
    <>
      {/* Mobile toggle */}
      <button
        onClick={() => setMobileOpen(!mobileOpen)}
        className="lg:hidden fixed top-4 left-4 z-50 p-2 rounded-lg bg-white border border-[#E5E5E5]"
      >
        {mobileOpen ? (
          <X className="w-5 h-5" />
        ) : (
          <Menu className="w-5 h-5" />
        )}
      </button>

      {/* Mobile overlay */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setMobileOpen(false)}
            className="lg:hidden fixed inset-0 bg-black/50 backdrop-blur-sm z-40"
          />
        )}
      </AnimatePresence>

      {/* Sidebar */}
      <motion.aside
        initial={false}
        animate={{ width: collapsed ? 64 : 220 }}
        className={cn(
          "fixed left-0 top-0 h-screen bg-sidebar-background/90 backdrop-blur-xl border-r border-sidebar-border z-40 flex flex-col",
          "lg:relative",
          mobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        )}
      >
        {/* Collapse toggle */}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="hidden lg:flex absolute -right-3 top-6 z-50 w-6 h-6 rounded-full bg-white border border-[#E5E5E5] items-center justify-center hover:bg-[#F4F3EF]"
        >
          <ChevronDown
            className={cn(
              "w-3 h-3 transition-transform",
              collapsed ? "rotate-90" : "-rotate-90"
            )}
          />
        </button>

        {sidebarContent}
      </motion.aside>
    </>
  )
}
