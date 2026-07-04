import { useState, useEffect } from "react"
import { motion } from "framer-motion"
import {
  Settings,
  Save,
  Loader2,
  CheckCircle2,
  Brain,
  Key,
  Sliders,
  TestTube,
  Activity,
  Shield,
  Database,
  HardDrive,
  XCircle,
  AlertCircle,
  Globe,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { api } from "@/api/client"

const defaultProviders = [
  { id: "deepseek", label: "DeepSeek", desc: "高性价比，推荐" },
  { id: "openai", label: "OpenAI", desc: "GPT-4o" },
  { id: "claude", label: "Claude", desc: "复杂推理" },
]

interface BrainItem {
  brain_id: string
  name: string
  provider: string
  description: string
  icon: string
  enabled: boolean
}

interface SystemHealth {
  backend: boolean
  database: boolean
  apiConfigured: boolean
  currentProvider: string
  browserApproved: boolean
  hermesAvailable: boolean
  version: string
}

export default function SettingsPage() {
  const [provider, setProvider] = useState("deepseek")
  const [apiKey, setApiKey] = useState("")
  const [model, setModel] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [isSaved, setIsSaved] = useState(false)
  const [isTesting, setIsTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null)
  const [health, setHealth] = useState<SystemHealth>({
    backend: false,
    database: false,
    apiConfigured: false,
    currentProvider: "deepseek",
    browserApproved: false,
    hermesAvailable: false,
    version: "unknown",
  })
  const [loadingHealth, setLoadingHealth] = useState(true)
  const [providers, setProviders] = useState(defaultProviders)
  const [brains, setBrains] = useState<BrainItem[]>([])
  const [currentBrain, setCurrentBrain] = useState("")
  const [switchingBrain, setSwitchingBrain] = useState("")

  useEffect(() => {
    loadConfig()
    loadHealth()
    loadProviders()
    loadBrains()
  }, [])

  const loadConfig = async () => {
    try {
      const config = await api.getConfig()
      setProvider(config.current_provider || "deepseek")
    } catch (error) {
      console.error("Failed to load config:", error)
    }
  }

  const loadProviders = async () => {
    try {
      const res = await api.getProviders()
      if (res.providers && res.providers.length > 0) {
        setProviders(res.providers.map((p: Record<string, unknown>) => ({
          id: p.id as string,
          label: (p.name as string) || (p.id as string),
          desc: (p.description as string) || "",
        })))
      }
    } catch {
      // keep defaults
    }
  }

  const loadBrains = async () => {
    try {
      const res = await api.getBrains()
      setBrains(res.brains || [])
      setCurrentBrain(res.current?.brain_id || "")
    } catch {
      // ignore
    }
  }

  const handleSwitchBrain = async (brainId: string) => {
    setSwitchingBrain(brainId)
    try {
      await api.switchBrain(brainId)
      setCurrentBrain(brainId)
    } catch (e) {
      console.error("Failed to switch brain:", e)
    } finally {
      setSwitchingBrain("")
    }
  }

  const loadHealth = async () => {
    setLoadingHealth(true)
    try {
      // Check backend health
      let backendOk = false
      let version = "unknown"
      try {
        const h = await api.healthCheck()
        backendOk = h.status === "ok" || h.status === "healthy"
        version = h.version || "unknown"
      } catch {
        backendOk = false
      }

      // Check config for API key status
      let apiConfigured = false
      let currentProvider = "deepseek"
      try {
        const config = await api.getConfig()
        currentProvider = config.current_provider || "deepseek"
        // Check if provider has key configured
        const providerInfo = config.providers?.find(
          (p: Record<string, unknown>) => p.id === currentProvider
        )
        if (providerInfo) {
          apiConfigured = !!(providerInfo as Record<string, unknown>).configured
        }
      } catch {
        // ignore
      }

      // Check capabilities for hermes
      let hermesAvailable = false
      try {
        const caps = await fetch("/capabilities").then((r) => r.json())
        hermesAvailable = caps.hermes?.available || false
      } catch {
        // ignore
      }

      setHealth({
        backend: backendOk,
        database: backendOk, // If backend is up, DB is up
        apiConfigured,
        currentProvider,
        browserApproved: false, // Never auto-true
        hermesAvailable,
        version,
      })
    } catch {
      // ignore
    } finally {
      setLoadingHealth(false)
    }
  }

  const handleSave = async () => {
    setIsLoading(true)
    try {
      const configData: Record<string, unknown> = {
        ai_provider: provider,
      }

      if (apiKey) {
        configData[`${provider}_api_key`] = apiKey
      }

      if (model) {
        configData[`${provider}_model`] = model
      }

      await api.saveConfig(configData)
      setIsSaved(true)
      setTimeout(() => setIsSaved(false), 2000)
      loadHealth() // Refresh health
    } catch (error) {
      console.error("Failed to save config:", error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleTest = async () => {
    setIsTesting(true)
    setTestResult(null)
    try {
      const result = await api.testConnection(provider)
      setTestResult(result)
    } catch (error) {
      setTestResult({ ok: false, message: "连接测试失败" })
    } finally {
      setIsTesting(false)
    }
  }

  const HealthItem = ({
    label,
    available,
    icon: Icon,
    fixHint,
  }: {
    label: string
    available: boolean
    icon: React.ElementType
    fixHint?: string
  }) => (
    <div className="flex items-center justify-between py-3 border-b border-border last:border-0">
      <div className="flex items-center gap-3">
        <div
          className={`w-8 h-8 rounded-lg flex items-center justify-center ${
            available ? "bg-green/10" : "bg-destructive/10"
          }`}
        >
          <Icon className={`w-4 h-4 ${available ? "text-green" : "text-destructive"}`} />
        </div>
        <div>
          <span className="text-sm font-medium">{label}</span>
          {fixHint && !available && (
            <p className="text-xs text-muted-foreground mt-0.5">{fixHint}</p>
          )}
        </div>
      </div>
      {available ? (
        <Badge variant="success" className="text-xs">
          <CheckCircle2 className="w-3 h-3 mr-1" />
          可用
        </Badge>
      ) : (
        <Badge variant="destructive" className="text-xs">
          <XCircle className="w-3 h-3 mr-1" />
          不可用
        </Badge>
      )}
    </div>
  )

  return (
    <div className="space-y-6">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center gap-3"
      >
        <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
          <Settings className="w-6 h-6 text-primary" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">设置</h1>
          <p className="text-[#8A8A8A]">配置 AI 模型和系统参数</p>
        </div>
      </motion.div>

      {/* System Health Card */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="p-6 rounded-2xl border border-[#E5E5E5] bg-white"
      >
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Activity className="w-5 h-5 text-[#0B0B0B]" />
            <h3 className="font-semibold">系统健康</h3>
          </div>
          <Button variant="ghost" size="sm" onClick={loadHealth} disabled={loadingHealth}>
            <Loader2 className={`w-3.5 h-3.5 ${loadingHealth ? "animate-spin" : ""}`} />
            刷新
          </Button>
        </div>

        <div className="space-y-0">
          <HealthItem
            label="后端服务"
            available={health.backend}
            icon={HardDrive}
            fixHint="请确保后端已启动 (python backend/app.py)"
          />
          <HealthItem
            label="数据库"
            available={health.database}
            icon={Database}
          />
          <HealthItem
            label={`AI 模型 (${health.currentProvider})`}
            available={health.apiConfigured}
            icon={Brain}
            fixHint="请在下方配置 API Key"
          />
          <HealthItem
            label="Hermes Agent"
            available={health.hermesAvailable}
            icon={Globe}
            fixHint="需要配置 Hermes 才能使用浏览器采集"
          />
          <HealthItem
            label="浏览器采集授权"
            available={health.browserApproved}
            icon={Shield}
            fixHint="需要在 Boss 指挥台手动授权"
          />
        </div>

        {health.version && health.version !== "unknown" && (
          <div className="mt-4 pt-3 border-t border-border flex items-center justify-between text-xs text-muted-foreground">
            <span>系统版本</span>
            <span>{health.version}</span>
          </div>
        )}
      </motion.div>

      {/* Provider Selection */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
        className="p-6 rounded-2xl border border-[#E5E5E5] bg-white"
      >
        <div className="flex items-center gap-2 mb-4">
          <Brain className="w-5 h-5 text-[#0B0B0B]" />
          <h3 className="font-semibold">AI Provider</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {providers.map((p) => (
            <Button
              key={p.id}
              variant={provider === p.id ? "default" : "outline"}
              onClick={() => setProvider(p.id)}
              className="flex-col h-auto py-4"
            >
              <span className="font-semibold">{p.label}</span>
              <span className="text-xs opacity-70">{p.desc}</span>
            </Button>
          ))}
        </div>
      </motion.div>

      {/* Brain Selection — always render to avoid Framer Motion DOM conflicts */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.18 }}
        className="p-6 rounded-2xl border border-[#E5E5E5] bg-white"
        style={{ display: brains.length > 0 ? "block" : "none" }}
      >
          <div className="flex items-center gap-2 mb-4">
            <Brain className="w-5 h-5 text-[#0B0B0B]" />
            <h3 className="font-semibold">Brain 模式</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {brains.map((b) => (
              <button
                key={b.brain_id}
                onClick={() => handleSwitchBrain(b.brain_id)}
                disabled={switchingBrain === b.brain_id || currentBrain === b.brain_id}
                className={`p-4 rounded-xl border text-left transition-all ${
                  currentBrain === b.brain_id
                    ? "border-[#0B0B0B] bg-[#F4F3EF]"
                    : "border-[#E5E5E5] bg-white hover:border-[#B5B5B5]"
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-lg">{b.icon || "🧠"}</span>
                  <span className="font-medium text-sm">{b.name}</span>
                  {currentBrain === b.brain_id && (
                    <Badge variant="success" className="text-[10px] ml-auto">当前</Badge>
                  )}
                </div>
                <p className="text-xs text-[#8A8A8A]">{b.description}</p>
                <p className="text-[10px] text-[#D4D4D4] mt-1">{b.provider}</p>
              </button>
            ))}
          </div>
        </motion.div>

      {/* API Key */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="p-6 rounded-2xl border border-[#E5E5E5] bg-white"
      >
        <div className="flex items-center gap-2 mb-4">
          <Key className="w-5 h-5 text-[#0B0B0B]" />
          <h3 className="font-semibold">API Key</h3>
          {health.apiConfigured && (
            <Badge variant="success" className="text-xs ml-2">
              <CheckCircle2 className="w-3 h-3 mr-1" />
              已配置
            </Badge>
          )}
          {!health.apiConfigured && health.backend && (
            <Badge variant="warning" className="text-xs ml-2">
              <AlertCircle className="w-3 h-3 mr-1" />
              未配置
            </Badge>
          )}
        </div>
        <Input
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder={`输入 ${provider.toUpperCase()} API Key（留空保持当前配置）`}
        />
        <p className="text-xs text-[#8A8A8A] mt-2">
          获取 API Key：
          {provider === "deepseek" && " https://platform.deepseek.com"}
          {provider === "openai" && " https://platform.openai.com"}
          {provider === "claude" && " https://console.anthropic.com"}
        </p>
      </motion.div>

      {/* Model */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.25 }}
        className="p-6 rounded-2xl border border-[#E5E5E5] bg-white"
      >
        <div className="flex items-center gap-2 mb-4">
          <Sliders className="w-5 h-5 text-[#0B0B0B]" />
          <h3 className="font-semibold">Model</h3>
        </div>
        <Input
          value={model}
          onChange={(e) => setModel(e.target.value)}
          placeholder={`模型名称（留空使用默认: ${
            provider === "deepseek"
              ? "deepseek-chat"
              : provider === "openai"
                ? "gpt-4o"
                : "claude-sonnet-4-20250514"
          }）`}
        />
      </motion.div>

      {/* Test Connection */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="p-6 rounded-2xl border border-[#E5E5E5] bg-white"
      >
        <div className="flex items-center gap-2 mb-4">
          <TestTube className="w-5 h-5 text-[#0B0B0B]" />
          <h3 className="font-semibold">测试连接</h3>
        </div>
        <Button
          onClick={handleTest}
          disabled={isTesting}
          variant="outline"
          className="w-full"
        >
          {isTesting ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <TestTube className="w-4 h-4" />
          )}
          {isTesting ? "测试中..." : "测试连接"}
        </Button>
        {testResult && (
          <div
            className={`mt-3 p-3 rounded-lg text-sm ${
              testResult.ok
                ? "bg-green/10 text-green border border-green/20"
                : "bg-destructive/10 text-destructive border border-destructive/20"
            }`}
          >
            {testResult.message}
          </div>
        )}
      </motion.div>

      {/* Save Button */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.35 }}
      >
        <Button
          onClick={handleSave}
          disabled={isLoading}
          variant="default"
          size="lg"
          className="w-full"
        >
          {isLoading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : isSaved ? (
            <CheckCircle2 className="w-4 h-4 text-green" />
          ) : (
            <Save className="w-4 h-4" />
          )}
          {isSaved ? "已保存" : "保存设置"}
        </Button>
      </motion.div>
    </div>
  )
}
