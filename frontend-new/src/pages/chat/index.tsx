import { useState, useRef, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Send, Sparkles, User, Bot, Loader2, Copy, Check, RefreshCw, AlertTriangle, Settings } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { useChatStore, type Message } from "@/stores/chat"
import { api } from "@/api/client"
import { cn } from "@/lib/utils"
import { useAppStore } from "@/stores/app"

function MessageBubble({ message, onRetry }: { message: Message; onRetry?: () => void }) {
  const isUser = message.role === "user"
  const isError = message.isError
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn("flex gap-3 max-w-[85%]", isUser ? "ml-auto" : "mr-auto")}
    >
      {!isUser && (
        <div className={cn(
          "w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0",
          isError
            ? "bg-destructive/10"
            : "bg-primary/10"
        )}>
          {isError ? (
            <AlertTriangle className="w-4 h-4 text-destructive" />
          ) : (
            <Bot className="w-4 h-4 text-primary" />
          )}
        </div>
      )}

      <div className="group relative">
        <div
          className={cn(
            "rounded-2xl px-4 py-3 text-sm",
            isUser
              ? "bg-primary text-primary-foreground rounded-br-md"
              : isError
                ? "bg-destructive/5 border border-destructive/20 rounded-bl-md"
                : "bg-card border border-border rounded-bl-md"
          )}
        >
          {message.content}
        </div>

        {/* Copy + Retry buttons */}
        {!isUser && (
          <div className="absolute -right-8 top-2 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col gap-1">
            <button
              onClick={handleCopy}
              className="p-1 rounded hover:bg-accent"
            >
              {copied ? (
                <Check className="w-3 h-3 text-green" />
              ) : (
                <Copy className="w-3 h-3 text-muted-foreground" />
              )}
            </button>
            {isError && onRetry && (
              <button
                onClick={onRetry}
                className="p-1 rounded hover:bg-accent"
                title="重试"
              >
                <RefreshCw className="w-3 h-3 text-muted-foreground" />
              </button>
            )}
          </div>
        )}
      </div>

      {isUser && (
        <div className="w-8 h-8 rounded-lg bg-secondary flex items-center justify-center flex-shrink-0">
          <User className="w-4 h-4" />
        </div>
      )}
    </motion.div>
  )
}

function TypingIndicator() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className="flex gap-3 max-w-[85%] mr-auto"
    >
      <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
        <Bot className="w-4 h-4 text-primary" />
      </div>
      <div className="bg-card border border-border rounded-2xl rounded-bl-md px-4 py-3">
        <div className="flex items-center gap-2">
          <Loader2 className="w-4 h-4 animate-spin text-primary" />
          <span className="text-sm text-muted-foreground">正在思考...</span>
        </div>
      </div>
    </motion.div>
  )
}

function ApiKeyWarning() {
  const setCurrentPage = useAppStore((s) => s.setCurrentPage)

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="mx-4 p-4 rounded-xl border border-yellow/30 bg-yellow/5"
    >
      <div className="flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 text-yellow mt-0.5 shrink-0" />
        <div className="flex-1">
          <h4 className="font-medium text-sm mb-1">AI 模型未配置</h4>
          <p className="text-sm text-muted-foreground mb-3">
            需要配置 API Key 才能使用 AI 对话功能。
          </p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCurrentPage("settings")}
            className="gap-2"
          >
            <Settings className="w-3.5 h-3.5" />
            前往设置
          </Button>
        </div>
      </div>
    </motion.div>
  )
}

export default function ChatPage() {
  const [input, setInput] = useState("")
  const [apiStatus, setApiStatus] = useState<"unknown" | "ok" | "missing_key">("unknown")
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const { messages, isLoading, addMessage, setLoading, clearMessages } = useChatStore()
  const pendingMessage = useAppStore((s) => s.pendingMessage)
  const setPendingMessage = useAppStore((s) => s.setPendingMessage)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Check API status on mount
  useEffect(() => {
    const checkApi = async () => {
      try {
        const config = await api.getConfig()
        const provider = config.current_provider || "deepseek"
        const providerInfo = config.providers?.find((p: Record<string, unknown>) => p.id === provider)
        if (providerInfo && !(providerInfo as Record<string, unknown>).configured) {
          setApiStatus("missing_key")
        } else {
          setApiStatus("ok")
        }
      } catch {
        // If we can't reach config endpoint, don't block
        setApiStatus("unknown")
      }
    }
    checkApi()
  }, [])

  // Auto-send pending message from home page
  useEffect(() => {
    if (pendingMessage && messages.length === 0 && !isLoading) {
      const msg = pendingMessage
      setPendingMessage(null)
      // Use setTimeout to ensure state is ready
      setTimeout(() => {
        setInput("")
        addMessage({ role: "user", content: msg })
        setLoading(true)
        api.chat(msg, []).then((response) => {
          addMessage({ role: "assistant", content: response.reply })
          setApiStatus("ok")
        }).catch((error) => {
          addMessage({
            role: "assistant",
            content: error instanceof Error ? error.message : "发送失败",
            isError: true,
          })
        }).finally(() => {
          setLoading(false)
        })
      }, 100)
    }
  }, [pendingMessage])

  const handleSend = async (retryMessage?: string) => {
    const messageToSend = retryMessage || input.trim()
    if (!messageToSend || isLoading) return

    if (!retryMessage) {
      setInput("")
    }
    addMessage({ role: "user", content: messageToSend })
    setLoading(true)

    try {
      const history = messages.slice(-20).map((msg) => ({
        role: msg.role,
        content: msg.content,
      }))

      const response = await api.chat(messageToSend, history)
      addMessage({ role: "assistant", content: response.reply })
      setApiStatus("ok")
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : "未知错误"

      // Detect specific error types
      let userMessage = "抱歉，发生了错误。请稍后重试。"
      if (errorMsg.includes("API key") || errorMsg.includes("api_key") || errorMsg.includes("401")) {
        userMessage = "API Key 未配置或已失效。请前往设置页面配置正确的 API Key。"
        setApiStatus("missing_key")
      } else if (errorMsg.includes("429") || errorMsg.includes("rate")) {
        userMessage = "请求太频繁了，请稍等一会再试。"
      } else if (errorMsg.includes("network") || errorMsg.includes("fetch")) {
        userMessage = "网络连接失败，请检查网络后重试。"
      } else if (errorMsg.includes("timeout")) {
        userMessage = "请求超时，AI 可能正在处理较复杂的任务，请稍后重试。"
      }

      addMessage({
        role: "assistant",
        content: userMessage,
        isError: true,
      })
    } finally {
      setLoading(false)
    }
  }

  const handleRetry = () => {
    // Find last user message
    const lastUserMsg = [...messages].reverse().find((m) => m.role === "user")
    if (lastUserMsg) {
      // Remove last error message
      clearMessagesOnError()
      handleSend(lastUserMsg.content)
    }
  }

  const clearMessagesOnError = () => {
    // Remove last assistant error message
    const store = useChatStore.getState()
    const msgs = store.messages
    if (msgs.length > 0 && msgs[msgs.length - 1].isError) {
      useChatStore.setState({ messages: msgs.slice(0, -1) })
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
            <Sparkles className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold">AI 助手</h1>
            <p className="text-sm text-muted-foreground">
              有什么可以帮你的？
            </p>
          </div>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={clearMessages}
          className="gap-2"
        >
          <RefreshCw className="w-4 h-4" />
          新对话
        </Button>
      </div>

      {/* API Key Warning */}
      {apiStatus === "missing_key" && messages.length === 0 && <ApiKeyWarning />}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 p-4 rounded-xl bg-background/50 border border-border">
        {messages.length === 0 ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex flex-col items-center justify-center h-full text-center"
          >
            <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mb-4">
              <Sparkles className="w-8 h-8 text-primary" />
            </div>
            <h3 className="text-lg font-semibold mb-2">开始对话</h3>
            <p className="text-muted-foreground max-w-sm mb-6">
              我可以帮你写文案、分析数据、做调研、建网站...
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-md">
              {[
                { text: "帮我写一条推广手工耳环的朋友圈文案", icon: "📝" },
                { text: "给我一些小红书爆款标题的建议", icon: "💡" },
                { text: "帮我分析一下手工饰品的目标客户群体", icon: "📊" },
                { text: "帮我做一个产品介绍页面", icon: "🌐" },
              ].map((prompt, i) => (
                <motion.button
                  key={i}
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.2 + i * 0.1 }}
                  onClick={() => setInput(prompt.text)}
                  className="flex items-start gap-2 p-3 rounded-lg border border-border text-left text-sm text-muted-foreground hover:text-foreground hover:border-primary/50 hover:bg-primary/5 transition-all"
                >
                  <span className="text-lg">{prompt.icon}</span>
                  <span>{prompt.text}</span>
                </motion.button>
              ))}
            </div>
          </motion.div>
        ) : (
          <>
            <AnimatePresence>
              {messages.map((message) => (
                <MessageBubble
                  key={message.id}
                  message={message}
                  onRetry={message.isError ? handleRetry : undefined}
                />
              ))}
            </AnimatePresence>
            {isLoading && <TypingIndicator />}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="mt-4 flex gap-3">
        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="输入你的问题..."
          className="min-h-[60px] text-base"
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault()
              handleSend()
            }
          }}
        />
        <Button
          onClick={() => handleSend()}
          disabled={!input.trim() || isLoading}
          size="lg"
          className="self-end px-6"
        >
          {isLoading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Send className="w-4 h-4" />
          )}
          发送
        </Button>
      </div>
    </div>
  )
}
