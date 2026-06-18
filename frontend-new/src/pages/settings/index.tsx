import { useState, useEffect } from "react"
import { Settings, Save, Loader2, CheckCircle2, Brain, Key, Sliders, TestTube } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { GlowCard } from "@/components/shared/glow-card"
import { api } from "@/api/client"

const providers = [
  { id: "deepseek", label: "DeepSeek", desc: "Cost-effective, recommended" },
  { id: "openai", label: "OpenAI", desc: "GPT-4o" },
  { id: "claude", label: "Claude", desc: "Complex reasoning" },
]

export default function SettingsPage() {
  const [provider, setProvider] = useState("deepseek")
  const [apiKey, setApiKey] = useState("")
  const [model, setModel] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [isSaved, setIsSaved] = useState(false)
  const [isTesting, setIsTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null)

  useEffect(() => {
    loadConfig()
  }, [])

  const loadConfig = async () => {
    try {
      const config = await api.getConfig()
      setProvider(config.current_provider || "deepseek")
    } catch (error) {
      console.error("Failed to load config:", error)
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
      setTestResult({ ok: false, message: "Test failed" })
    } finally {
      setIsTesting(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-gray-500 to-gray-600 flex items-center justify-center">
          <Settings className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">Settings</h1>
          <p className="text-muted-foreground">Configure AI Provider and system settings</p>
        </div>
      </div>

      {/* Provider Selection */}
      <GlowCard>
        <div className="flex items-center gap-2 mb-4">
          <Brain className="w-5 h-5 text-primary" />
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
      </GlowCard>

      {/* API Key */}
      <GlowCard>
        <div className="flex items-center gap-2 mb-4">
          <Key className="w-5 h-5 text-primary" />
          <h3 className="font-semibold">API Key</h3>
        </div>
        <Input
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder={`Enter your ${provider.toUpperCase()} API Key (leave empty to keep current)`}
        />
        <p className="text-xs text-muted-foreground mt-2">
          Get API Key from:{" "}
          {provider === "deepseek" && "https://platform.deepseek.com"}
          {provider === "openai" && "https://platform.openai.com"}
          {provider === "claude" && "https://console.anthropic.com"}
        </p>
      </GlowCard>

      {/* Model */}
      <GlowCard>
        <div className="flex items-center gap-2 mb-4">
          <Sliders className="w-5 h-5 text-primary" />
          <h3 className="font-semibold">Model</h3>
        </div>
        <Input
          value={model}
          onChange={(e) => setModel(e.target.value)}
          placeholder={`Model name (leave empty to use default: ${provider === "deepseek" ? "deepseek-chat" : provider === "openai" ? "gpt-4o" : "claude-sonnet-4-20250514"})`}
        />
      </GlowCard>

      {/* Test Connection */}
      <GlowCard>
        <div className="flex items-center gap-2 mb-4">
          <TestTube className="w-5 h-5 text-primary" />
          <h3 className="font-semibold">Test Connection</h3>
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
          {isTesting ? "Testing..." : "Test Connection"}
        </Button>
        {testResult && (
          <div className={`mt-3 p-3 rounded-lg ${testResult.ok ? "bg-green/10 text-green" : "bg-red/10 text-red"}`}>
            {testResult.message}
          </div>
        )}
      </GlowCard>

      {/* Save Button */}
      <Button
        onClick={handleSave}
        disabled={isLoading}
        variant="glow"
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
        {isSaved ? "Saved!" : "Save Settings"}
      </Button>
    </div>
  )
}
