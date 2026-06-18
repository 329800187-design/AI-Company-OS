import { useState, useRef, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Send, Sparkles, User, Bot, Loader2, Copy, Check, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { useChatStore, type Message } from "@/stores/chat"
import { api } from "@/api/client"
import { cn } from "@/lib/utils"

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user"
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
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-cyan flex items-center justify-center flex-shrink-0">
          <Bot className="w-4 h-4 text-white" />
        </div>
      )}

      <div className="group relative">
        <div
          className={cn(
            "rounded-2xl px-4 py-3 text-sm",
            isUser
              ? "bg-primary text-primary-foreground rounded-br-md"
              : "bg-card border border-border rounded-bl-md"
          )}
        >
          {message.content}
        </div>

        {/* Copy button */}
        {!isUser && (
          <button
            onClick={handleCopy}
            className="absolute -right-8 top-2 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-accent"
          >
            {copied ? (
              <Check className="w-3 h-3 text-green" />
            ) : (
              <Copy className="w-3 h-3 text-muted-foreground" />
            )}
          </button>
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
      <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-cyan flex items-center justify-center flex-shrink-0">
        <Bot className="w-4 h-4 text-white" />
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

export default function ChatPage() {
  const [input, setInput] = useState("")
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const { messages, isLoading, addMessage, setLoading, clearMessages } = useChatStore()

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSend = async () => {
    if (!input.trim() || isLoading) return

    const userMessage = input.trim()
    setInput("")
    addMessage({ role: "user", content: userMessage })
    setLoading(true)

    try {
      // 构建历史记录（最近 10 轮对话）
      const history = messages.slice(-20).map((msg) => ({
        role: msg.role,
        content: msg.content,
      }))

      const response = await api.chat(userMessage, history)
      addMessage({ role: "assistant", content: response.reply })
    } catch (error) {
      addMessage({
        role: "assistant",
        content: "抱歉，发生了错误。请检查网络连接后重试。",
      })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-cyan flex items-center justify-center">
            <Sparkles className="w-5 h-5 text-white" />
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

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 p-4 rounded-xl bg-background/50 border border-border">
        {messages.length === 0 ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex flex-col items-center justify-center h-full text-center"
          >
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary/20 to-cyan/20 flex items-center justify-center mb-4">
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
                <MessageBubble key={message.id} message={message} />
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
          onClick={handleSend}
          disabled={!input.trim() || isLoading}
          size="lg"
          variant="glow"
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
