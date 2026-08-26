import { useCallback, useEffect, useMemo, useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import {
  AlertTriangle,
  BookOpen,
  Brain,
  Clock,
  Edit3,
  Filter,
  Plus,
  RefreshCw,
  Search,
  Tag,
  Trash2,
  X,
} from "lucide-react"
import { api } from "@/api/client"

interface Memory {
  key: string
  content: string
  source: string
  tags: string[]
  importance: number
  created_at: string
  accessed_at: string
  access_count: number
}

interface MemoryForm {
  key: string
  content: string
  source: string
  tags: string
  importance: number
}

const emptyForm: MemoryForm = {
  key: "",
  content: "",
  source: "user",
  tags: "",
  importance: 0.5,
}

const sourceOptions = [
  { value: "all", label: "全部来源" },
  { value: "user", label: "用户" },
  { value: "agent", label: "Agent" },
  { value: "api", label: "API" },
  { value: "learned", label: "学习" },
  { value: "other", label: "其他" },
]

const importanceOptions = [
  { value: "all", label: "全部重要性" },
  { value: "high", label: "高" },
  { value: "medium", label: "中" },
  { value: "low", label: "低" },
]

function toTags(value: string) {
  return value
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean)
}

function toForm(memory: Memory): MemoryForm {
  return {
    key: memory.key,
    content: memory.content,
    source: memory.source || "user",
    tags: memory.tags.join(", "),
    importance: memory.importance ?? 0.5,
  }
}

function sourceLabel(source: string) {
  const option = sourceOptions.find((item) => item.value === source)
  return option?.label ?? source
}

function sourceIcon(source: string) {
  if (source === "user") return "👤"
  if (source === "api") return "🔗"
  if (source === "agent") return "🤖"
  if (source === "learned") return "📘"
  return "📌"
}

function importanceLabel(importance: number) {
  if (importance >= 0.8) return "高"
  if (importance >= 0.5) return "中"
  return "低"
}

function importanceClass(importance: number) {
  if (importance >= 0.8) return "text-red-400 bg-red-500/10 border-red-500/20"
  if (importance >= 0.5) return "text-amber-400 bg-amber-500/10 border-amber-500/20"
  return "text-zinc-400 bg-zinc-500/10 border-zinc-500/20"
}

export default function MemoryPage() {
  const [memories, setMemories] = useState<Memory[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState("")
  const [sourceFilter, setSourceFilter] = useState("all")
  const [importanceFilter, setImportanceFilter] = useState("all")
  const [error, setError] = useState("")
  const [showAdd, setShowAdd] = useState(false)
  const [addForm, setAddForm] = useState<MemoryForm>(emptyForm)
  const [editingMemory, setEditingMemory] = useState<Memory | null>(null)
  const [editForm, setEditForm] = useState<MemoryForm>(emptyForm)
  const [saving, setSaving] = useState(false)
  const [deletingKey, setDeletingKey] = useState<string | null>(null)
  const [deleteConfirmKey, setDeleteConfirmKey] = useState<string | null>(null)
  const [clearConfirm, setClearConfirm] = useState(false)
  const [clearing, setClearing] = useState(false)

  const loadMemories = useCallback(async () => {
    setLoading(true)
    setError("")
    try {
      const query = searchQuery.trim()
      const response = query ? await api.searchMemory(query, 100) : await api.recentMemory(100)
      setMemories(response.memories)
    } catch {
      setError("无法加载知识库，请确认后端服务正在运行")
    } finally {
      setLoading(false)
    }
  }, [searchQuery])

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void loadMemories()
    }, 0)

    return () => window.clearTimeout(timeoutId)
  }, [loadMemories])

  const filteredMemories = useMemo(() => {
    return memories.filter((memory) => {
      if (sourceFilter !== "all") {
        if (sourceFilter === "other") {
          const knownSources = ["user", "agent", "api", "learned"]
          if (knownSources.includes(memory.source)) return false
        } else if (memory.source !== sourceFilter) {
          return false
        }
      }

      if (importanceFilter === "high" && memory.importance < 0.8) return false
      if (importanceFilter === "medium" && (memory.importance < 0.5 || memory.importance >= 0.8)) return false
      if (importanceFilter === "low" && memory.importance >= 0.5) return false

      return true
    })
  }, [importanceFilter, memories, sourceFilter])

  const stats = useMemo(() => {
    return {
      total: memories.length,
      high: memories.filter((memory) => memory.importance >= 0.8).length,
      sources: new Set(memories.map((memory) => memory.source)).size,
    }
  }, [memories])

  const resetSearch = () => {
    setSearchQuery("")
    setSourceFilter("all")
    setImportanceFilter("all")
  }

  const handleAdd = async () => {
    if (!addForm.key.trim() || !addForm.content.trim()) return
    setSaving(true)
    setError("")
    try {
      await api.rememberMemory(
        addForm.key.trim(),
        addForm.content.trim(),
        addForm.source,
        toTags(addForm.tags),
        addForm.importance,
      )
      setShowAdd(false)
      setAddForm(emptyForm)
      await loadMemories()
    } catch {
      setError("保存记忆失败")
    } finally {
      setSaving(false)
    }
  }

  const openEdit = (memory: Memory) => {
    setEditingMemory(memory)
    setEditForm(toForm(memory))
  }

  const handleEdit = async () => {
    if (!editingMemory || !editForm.content.trim()) return
    setSaving(true)
    setError("")
    try {
      await api.updateMemory(editingMemory.key, {
        content: editForm.content.trim(),
        source: editForm.source,
        tags: toTags(editForm.tags),
        importance: editForm.importance,
      })
      setEditingMemory(null)
      setEditForm(emptyForm)
      await loadMemories()
    } catch {
      setError("更新记忆失败")
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (key: string) => {
    setDeletingKey(key)
    setError("")
    try {
      await api.deleteMemory(key)
      setMemories((currentMemories) => currentMemories.filter((memory) => memory.key !== key))
      setDeleteConfirmKey(null)
    } catch {
      setError("删除记忆失败")
    } finally {
      setDeletingKey(null)
    }
  }

  const handleClearAll = async () => {
    setClearing(true)
    setError("")
    try {
      await api.clearMemory()
      setMemories([])
      setClearConfirm(false)
    } catch {
      setError("清空知识库失败")
    } finally {
      setClearing(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#0B0B0B] p-6">
      <div className="mx-auto max-w-6xl">
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="mb-8">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/5">
              <Brain className="h-5 w-5 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">知识库</h1>
              <p className="text-sm text-[#8A8A8A]">管理 AI 系统的长期记忆、来源和重要性</p>
            </div>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="mb-6 space-y-3"
        >
          <div className="flex flex-col gap-3 lg:flex-row">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#666]" />
              <input
                type="text"
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                onKeyDown={(event) => event.key === "Enter" && loadMemories()}
                placeholder="搜索记忆内容、key 或标签"
                className="w-full rounded-xl border border-white/10 bg-white/5 py-3 pl-10 pr-10 text-white placeholder-[#666] transition-colors focus:border-white/30 focus:outline-none"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery("")}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#666] hover:text-white"
                  aria-label="清空搜索"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
            <button
              onClick={loadMemories}
              disabled={loading}
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-white px-5 py-3 font-medium text-black transition-colors hover:bg-white/90 disabled:opacity-50"
            >
              <Search className="h-4 w-4" />
              搜索
            </button>
            <button
              onClick={() => setShowAdd(true)}
              className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/10 px-4 py-3 text-white transition-colors hover:bg-white/15"
            >
              <Plus className="h-4 w-4" />
              添加记忆
            </button>
            <button
              onClick={loadMemories}
              disabled={loading}
              className="inline-flex items-center justify-center rounded-xl border border-white/10 bg-white/10 px-4 py-3 text-white transition-colors hover:bg-white/15 disabled:opacity-50"
              aria-label="刷新"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            </button>
          </div>

          <div className="flex flex-col gap-3 md:flex-row md:items-center">
            <div className="flex items-center gap-2 text-xs text-[#8A8A8A]">
              <Filter className="h-4 w-4" />
              筛选
            </div>
            <select
              value={sourceFilter}
              onChange={(event) => setSourceFilter(event.target.value)}
              className="rounded-xl border border-white/10 bg-[#111] px-3 py-2 text-sm text-white focus:border-white/30 focus:outline-none"
            >
              {sourceOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <select
              value={importanceFilter}
              onChange={(event) => setImportanceFilter(event.target.value)}
              className="rounded-xl border border-white/10 bg-[#111] px-3 py-2 text-sm text-white focus:border-white/30 focus:outline-none"
            >
              {importanceOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            {(searchQuery || sourceFilter !== "all" || importanceFilter !== "all") && (
              <button onClick={resetSearch} className="text-sm text-[#8A8A8A] hover:text-white">
                重置条件
              </button>
            )}
          </div>
        </motion.div>

        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="mb-4 flex items-center gap-3 rounded-xl border border-red-500/20 bg-red-500/10 p-4"
            >
              <AlertTriangle className="h-4 w-4 flex-shrink-0 text-red-400" />
              <span className="text-sm text-red-300">{error}</span>
              <button onClick={() => setError("")} className="ml-auto text-red-400 hover:text-red-300">
                <X className="h-4 w-4" />
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="mb-6 grid gap-4 md:grid-cols-3"
        >
          <div className="rounded-xl border border-white/10 bg-white/5 p-4">
            <div className="text-2xl font-bold text-white">{stats.total}</div>
            <div className="mt-1 text-xs text-[#8A8A8A]">总记忆数</div>
          </div>
          <div className="rounded-xl border border-white/10 bg-white/5 p-4">
            <div className="text-2xl font-bold text-white">{stats.high}</div>
            <div className="mt-1 text-xs text-[#8A8A8A]">高重要性</div>
          </div>
          <div className="rounded-xl border border-white/10 bg-white/5 p-4">
            <div className="text-2xl font-bold text-white">{stats.sources}</div>
            <div className="mt-1 text-xs text-[#8A8A8A]">来源类型</div>
          </div>
        </motion.div>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="flex flex-col items-center gap-4">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-white border-t-transparent" />
              <p className="text-sm text-[#8A8A8A]">加载中...</p>
            </div>
          </div>
        ) : filteredMemories.length === 0 ? (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col items-center justify-center py-20">
            <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl border border-white/10 bg-white/5">
              <BookOpen className="h-8 w-8 text-[#666]" />
            </div>
            <h3 className="mb-2 text-lg font-medium text-white">
              {memories.length === 0 ? "还没有记忆" : "没有匹配的记忆"}
            </h3>
            <p className="mb-4 text-sm text-[#8A8A8A]">
              {memories.length === 0 ? "添加第一条记忆，让系统积累长期知识" : "尝试调整搜索或筛选条件"}
            </p>
            {memories.length === 0 && (
              <button onClick={() => setShowAdd(true)} className="rounded-lg bg-white px-4 py-2 text-sm font-medium text-black hover:bg-white/90">
                添加第一条记忆
              </button>
            )}
          </motion.div>
        ) : (
          <div className="space-y-3">
            {filteredMemories.map((memory, index) => (
              <motion.div
                key={memory.key}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.02 }}
                className="group rounded-xl border border-white/10 bg-white/5 p-4 transition-colors hover:border-white/20"
              >
                <div className="flex items-start gap-3">
                  <div className="mt-0.5 text-lg">{sourceIcon(memory.source)}</div>
                  <div className="min-w-0 flex-1">
                    <div className="mb-1 flex flex-wrap items-center gap-2">
                      <h3 className="truncate text-sm font-medium text-white">{memory.key}</h3>
                      <span className={`rounded-full border px-2 py-0.5 text-[10px] ${importanceClass(memory.importance)}`}>
                        {importanceLabel(memory.importance)}
                      </span>
                      <span className="rounded-full bg-white/5 px-2 py-0.5 text-[10px] text-[#8A8A8A]">
                        {sourceLabel(memory.source)}
                      </span>
                    </div>
                    <p className="mb-3 whitespace-pre-wrap break-words text-sm leading-6 text-[#B5B5B5]">{memory.content}</p>
                    <div className="flex flex-wrap items-center gap-3 text-[10px] text-[#666]">
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {memory.created_at ? new Date(memory.created_at).toLocaleString() : "未知时间"}
                      </span>
                      <span>访问 {memory.access_count} 次</span>
                      <span>重要性 {memory.importance.toFixed(1)}</span>
                    </div>
                    {memory.tags.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {memory.tags.map((tag) => (
                          <span key={tag} className="inline-flex items-center gap-1 rounded-full bg-white/5 px-2 py-0.5 text-[10px] text-[#8A8A8A]">
                            <Tag className="h-2.5 w-2.5" />
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-2 opacity-100 md:opacity-0 md:transition-opacity md:group-hover:opacity-100">
                    <button
                      onClick={() => openEdit(memory)}
                      className="rounded-lg border border-white/10 bg-white/10 p-2 text-[#8A8A8A] hover:text-white"
                      aria-label={`编辑 ${memory.key}`}
                    >
                      <Edit3 className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => setDeleteConfirmKey(memory.key)}
                      className="rounded-lg border border-red-500/20 bg-red-500/10 p-2 text-red-400 hover:bg-red-500/20"
                      aria-label={`删除 ${memory.key}`}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        )}

        {memories.length > 0 && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }} className="mt-8 border-t border-white/10 pt-6">
            {clearConfirm ? (
              <div className="flex flex-col gap-4 rounded-xl border border-red-500/20 bg-red-500/10 p-4 md:flex-row md:items-center">
                <AlertTriangle className="h-5 w-5 flex-shrink-0 text-red-400" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-red-300">确认清空所有记忆？</p>
                  <p className="mt-1 text-xs text-red-400/70">此操作不可恢复。</p>
                </div>
                <button
                  onClick={handleClearAll}
                  disabled={clearing}
                  className="rounded-lg bg-red-500 px-4 py-2 text-sm font-medium text-white hover:bg-red-600 disabled:opacity-50"
                >
                  {clearing ? "清空中..." : "确认清空"}
                </button>
                <button onClick={() => setClearConfirm(false)} className="rounded-lg bg-white/10 px-4 py-2 text-sm text-white hover:bg-white/15">
                  取消
                </button>
              </div>
            ) : (
              <button onClick={() => setClearConfirm(true)} className="flex items-center gap-2 text-sm text-[#666] transition-colors hover:text-red-400">
                <Trash2 className="h-3.5 w-3.5" />
                清空全部记忆
              </button>
            )}
          </motion.div>
        )}
      </div>

      <MemoryModal
        title="添加记忆"
        open={showAdd}
        form={addForm}
        setForm={setAddForm}
        saving={saving}
        submitLabel="保存"
        disableKey={false}
        onClose={() => setShowAdd(false)}
        onSubmit={handleAdd}
      />

      <MemoryModal
        title="编辑记忆"
        open={Boolean(editingMemory)}
        form={editForm}
        setForm={setEditForm}
        saving={saving}
        submitLabel="更新"
        disableKey
        onClose={() => setEditingMemory(null)}
        onSubmit={handleEdit}
      />

      <AnimatePresence>
        {deleteConfirmKey && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
            onClick={() => setDeleteConfirmKey(null)}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              onClick={(event) => event.stopPropagation()}
              className="w-full max-w-md rounded-2xl border border-white/10 bg-[#1A1A1A] p-6"
            >
              <div className="mb-4 flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-red-500/10 text-red-400">
                  <Trash2 className="h-5 w-5" />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-white">删除记忆</h2>
                  <p className="text-xs text-[#8A8A8A]">此操作不可恢复</p>
                </div>
              </div>
              <p className="mb-6 break-all text-sm text-[#B5B5B5]">确认删除 `{deleteConfirmKey}`？</p>
              <div className="flex gap-3">
                <button onClick={() => setDeleteConfirmKey(null)} className="flex-1 rounded-xl bg-white/10 px-4 py-2.5 text-sm text-white hover:bg-white/15">
                  取消
                </button>
                <button
                  onClick={() => handleDelete(deleteConfirmKey)}
                  disabled={deletingKey === deleteConfirmKey}
                  className="flex-1 rounded-xl bg-red-500 px-4 py-2.5 text-sm font-medium text-white hover:bg-red-600 disabled:opacity-50"
                >
                  {deletingKey === deleteConfirmKey ? "删除中..." : "确认删除"}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

interface MemoryModalProps {
  title: string
  open: boolean
  form: MemoryForm
  setForm: (form: MemoryForm) => void
  saving: boolean
  submitLabel: string
  disableKey: boolean
  onClose: () => void
  onSubmit: () => void
}

function MemoryModal({
  title,
  open,
  form,
  setForm,
  saving,
  submitLabel,
  disableKey,
  onClose,
  onSubmit,
}: MemoryModalProps) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
          onClick={onClose}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            onClick={(event) => event.stopPropagation()}
            className="w-full max-w-lg rounded-2xl border border-white/10 bg-[#1A1A1A] p-6"
          >
            <div className="mb-6 flex items-center justify-between">
              <h2 className="text-lg font-bold text-white">{title}</h2>
              <button onClick={onClose} className="text-[#666] hover:text-white">
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-4">
              <label className="block">
                <span className="mb-1.5 block text-xs text-[#8A8A8A]">Key</span>
                <input
                  type="text"
                  value={form.key}
                  disabled={disableKey}
                  onChange={(event) => setForm({ ...form, key: event.target.value })}
                  placeholder="例如 user-preference-language"
                  className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder-[#666] focus:border-white/30 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
                />
              </label>

              <label className="block">
                <span className="mb-1.5 block text-xs text-[#8A8A8A]">内容</span>
                <textarea
                  value={form.content}
                  onChange={(event) => setForm({ ...form, content: event.target.value })}
                  placeholder="记忆的具体内容"
                  rows={5}
                  className="w-full resize-none rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder-[#666] focus:border-white/30 focus:outline-none"
                />
              </label>

              <div className="grid gap-4 md:grid-cols-2">
                <label className="block">
                  <span className="mb-1.5 block text-xs text-[#8A8A8A]">来源</span>
                  <select
                    value={form.source}
                    onChange={(event) => setForm({ ...form, source: event.target.value })}
                    className="w-full rounded-xl border border-white/10 bg-[#111] px-4 py-2.5 text-sm text-white focus:border-white/30 focus:outline-none"
                  >
                    {sourceOptions
                      .filter((option) => option.value !== "all" && option.value !== "other")
                      .map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                  </select>
                </label>

                <label className="block">
                  <span className="mb-1.5 block text-xs text-[#8A8A8A]">重要性：{form.importance.toFixed(1)}</span>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.1"
                    value={form.importance}
                    onChange={(event) => setForm({ ...form, importance: Number(event.target.value) })}
                    className="w-full accent-white"
                  />
                </label>
              </div>

              <label className="block">
                <span className="mb-1.5 block text-xs text-[#8A8A8A]">标签，使用英文逗号分隔</span>
                <input
                  type="text"
                  value={form.tags}
                  onChange={(event) => setForm({ ...form, tags: event.target.value })}
                  placeholder="偏好, 工作流, 重要"
                  className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder-[#666] focus:border-white/30 focus:outline-none"
                />
              </label>
            </div>

            <div className="mt-6 flex gap-3">
              <button onClick={onClose} className="flex-1 rounded-xl bg-white/10 px-4 py-2.5 text-sm text-white hover:bg-white/15">
                取消
              </button>
              <button
                onClick={onSubmit}
                disabled={saving || !form.key.trim() || !form.content.trim()}
                className="flex-1 rounded-xl bg-white px-4 py-2.5 text-sm font-medium text-black hover:bg-white/90 disabled:opacity-50"
              >
                {saving ? "处理中..." : submitLabel}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
