import { useEffect, useState } from "react"
import { motion } from "framer-motion"
import {
  Puzzle,
  Search,
  Plus,
  X,
  RefreshCw,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { api } from "@/api/client"

interface Skill {
  name: string
  title: string
  description: string
  category: string
  capabilities: string[]
  triggers: string[]
}

export default function SkillsPage() {
  const [skills, setSkills] = useState<Skill[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState("")
  const [matches, setMatches] = useState<Array<{ name: string; title: string; score: number }>>([])
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ name: "", title: "", description: "", category: "general", capabilities: "", triggers: "", body: "" })
  const [saving, setSaving] = useState(false)

  const loadSkills = async () => {
    setLoading(true)
    try {
      const res = await api.listSkills()
      setSkills(res.skills || [])
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadSkills() }, [])

  const handleSearch = async () => {
    if (!searchQuery.trim()) { setMatches([]); return }
    try {
      const res = await api.matchSkills(searchQuery)
      setMatches(res.matched || [])
    } catch {
      setMatches([])
    }
  }

  const handleCreate = async () => {
    if (!form.name.trim() || !form.title.trim()) return
    setSaving(true)
    try {
      await api.createSkill({
        name: form.name.trim(),
        title: form.title.trim(),
        description: form.description.trim(),
        category: form.category.trim() || "general",
        capabilities: form.capabilities.split(",").map(s => s.trim()).filter(Boolean),
        triggers: form.triggers.split(",").map(s => s.trim()).filter(Boolean),
        body: form.body.trim(),
      })
      setShowCreate(false)
      setForm({ name: "", title: "", description: "", category: "general", capabilities: "", triggers: "", body: "" })
      loadSkills()
    } catch (e) {
      console.error("Failed to create skill:", e)
    } finally {
      setSaving(false)
    }
  }

  const categories = [...new Set(skills.map(s => s.category))]

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-violet-500 to-purple-500 flex items-center justify-center">
          <Puzzle className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">技能库</h1>
          <p className="text-sm text-[#8A8A8A]">{skills.length} 个已注册技能</p>
        </div>
      </div>

      {/* Search */}
      <div className="flex gap-3">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#666]" />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            placeholder="输入目标，匹配相关技能..."
            className="pl-10"
          />
        </div>
        <Button onClick={handleSearch} variant="outline">匹配</Button>
        <Button onClick={() => setShowCreate(true)}>
          <Plus className="w-4 h-4 mr-1" />创建技能
        </Button>
      </div>

      {/* Matches */}
      {matches.length > 0 && (
        <div className="p-4 rounded-2xl border border-violet-200 bg-violet-50">
          <h3 className="text-sm font-medium mb-2">匹配结果</h3>
          <div className="space-y-1">
            {matches.map(m => (
              <div key={m.name} className="flex items-center gap-2 text-sm">
                <Badge variant="outline" className="text-[10px]">{Math.round(m.score * 100)}%</Badge>
                <span className="font-medium">{m.title || m.name}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Skills List */}
      {loading ? (
        <div className="flex justify-center py-12">
          <RefreshCw className="w-6 h-6 animate-spin text-[#8A8A8A]" />
        </div>
      ) : skills.length === 0 ? (
        <div className="text-center py-12 text-[#8A8A8A]">暂无技能，点击"创建技能"添加</div>
      ) : (
        <div className="space-y-4">
          {categories.map(cat => (
            <div key={cat}>
              <h3 className="text-xs text-[#8A8A8A] uppercase tracking-wider mb-2">{cat}</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {skills.filter(s => s.category === cat).map(skill => (
                  <motion.div
                    key={skill.name}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="p-4 rounded-xl border border-[#E5E5E5] bg-white hover:border-[#B5B5B5] transition-colors"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <h4 className="font-medium text-sm">{skill.title || skill.name}</h4>
                      <Badge variant="outline" className="text-[10px] shrink-0">{skill.category}</Badge>
                    </div>
                    {skill.description && (
                      <p className="text-xs text-[#8A8A8A] mb-2 line-clamp-2">{skill.description}</p>
                    )}
                    {skill.capabilities.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {skill.capabilities.slice(0, 4).map((c, i) => (
                          <span key={i} className="text-[10px] px-2 py-0.5 rounded-full bg-[#F4F3EF] text-[#8A8A8A]">
                            {c}
                          </span>
                        ))}
                      </div>
                    )}
                  </motion.div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => setShowCreate(false)}>
          <div className="w-full max-w-lg rounded-2xl border border-[#E5E5E5] bg-white p-6" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold">创建技能</h2>
              <button onClick={() => setShowCreate(false)}><X className="w-5 h-5 text-[#8A8A8A]" /></button>
            </div>
            <div className="space-y-3">
              <Input placeholder="技能名称 (英文)" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
              <Input placeholder="显示标题" value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} />
              <Input placeholder="分类 (如: marketing, data)" value={form.category} onChange={e => setForm({ ...form, category: e.target.value })} />
              <textarea placeholder="描述" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} className="w-full rounded-xl border border-[#E5E5E5] px-3 py-2 text-sm min-h-[60px]" />
              <Input placeholder="能力 (逗号分隔)" value={form.capabilities} onChange={e => setForm({ ...form, capabilities: e.target.value })} />
              <Input placeholder="触发词 (逗号分隔)" value={form.triggers} onChange={e => setForm({ ...form, triggers: e.target.value })} />
              <textarea placeholder="技能内容 / Prompt" value={form.body} onChange={e => setForm({ ...form, body: e.target.value })} className="w-full rounded-xl border border-[#E5E5E5] px-3 py-2 text-sm min-h-[80px]" />
            </div>
            <div className="flex gap-3 mt-4">
              <Button variant="outline" onClick={() => setShowCreate(false)} className="flex-1">取消</Button>
              <Button onClick={handleCreate} disabled={saving || !form.name.trim() || !form.title.trim()} className="flex-1">
                {saving ? "创建中..." : "创建"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
