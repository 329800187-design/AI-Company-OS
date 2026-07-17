import { useEffect, useState } from "react"
import {
  Coins,
  Activity,
  Clock,
  RefreshCw,
  Zap,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { api } from "@/api/client"

export default function UsagePage() {
  const [total, setTotal] = useState<{ total_calls: number; total_tokens: number; total_cost_yuan: number } | null>(null)
  const [stats24h, setStats24h] = useState<{ hours: number; calls: number; tokens: number; cost_yuan: number } | null>(null)
  const [recent, setRecent] = useState<Array<{ model: string; tokens: number; cost_yuan: number; timestamp: string; duration_ms: number }>>([])
  const [loading, setLoading] = useState(true)

  const loadData = async () => {
    setLoading(true)
    try {
      const [t, s, r] = await Promise.all([
        api.getUsageTotal().catch(() => null),
        api.getUsageStats(24).catch(() => null),
        api.getUsageRecent(20).catch(() => ({ calls: [], count: 0 })),
      ])
      setTotal(t)
      setStats24h(s)
      setRecent(r.calls || [])
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadData() }, [])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-amber-500 to-orange-500 flex items-center justify-center">
            <Coins className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">用量统计</h1>
            <p className="text-sm text-[#8A8A8A]">AI API 调用次数、Token 消耗和费用追踪</p>
          </div>
        </div>
        <Button variant="outline" onClick={loadData} disabled={loading}>
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="p-5 rounded-2xl border border-[#E5E5E5] bg-white">
          <div className="flex items-center gap-2 mb-3">
            <Zap className="w-4 h-4 text-amber-500" />
            <span className="text-xs text-[#8A8A8A]">总调用次数</span>
          </div>
          <p className="text-2xl font-bold">{(total?.total_calls ?? 0).toLocaleString()}</p>
        </div>
        <div className="p-5 rounded-2xl border border-[#E5E5E5] bg-white">
          <div className="flex items-center gap-2 mb-3">
            <Activity className="w-4 h-4 text-blue-500" />
            <span className="text-xs text-[#8A8A8A]">总 Token</span>
          </div>
          <p className="text-2xl font-bold">{(total?.total_tokens ?? 0).toLocaleString()}</p>
        </div>
        <div className="p-5 rounded-2xl border border-[#E5E5E5] bg-white">
          <div className="flex items-center gap-2 mb-3">
            <Coins className="w-4 h-4 text-green" />
            <span className="text-xs text-[#8A8A8A]">总费用</span>
          </div>
          <p className="text-2xl font-bold">¥{(total?.total_cost_yuan ?? 0).toFixed(2)}</p>
        </div>
        <div className="p-5 rounded-2xl border border-[#E5E5E5] bg-white">
          <div className="flex items-center gap-2 mb-3">
            <Clock className="w-4 h-4 text-purple-500" />
            <span className="text-xs text-[#8A8A8A]">24h 调用</span>
          </div>
          <p className="text-2xl font-bold">{stats24h?.calls ?? 0}</p>
          <p className="text-xs text-[#8A8A8A] mt-1">¥{(stats24h?.cost_yuan ?? 0).toFixed(2)}</p>
        </div>
      </div>

      {/* Recent Calls */}
      <div className="p-6 rounded-2xl border border-[#E5E5E5] bg-white">
        <h3 className="font-semibold mb-4">最近调用记录</h3>
        {recent.length === 0 ? (
          <p className="text-sm text-[#8A8A8A] py-8 text-center">暂无调用记录</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[#8A8A8A] text-xs border-b border-border">
                  <th className="pb-2 font-medium">时间</th>
                  <th className="pb-2 font-medium">模型</th>
                  <th className="pb-2 font-medium text-right">Token</th>
                  <th className="pb-2 font-medium text-right">费用</th>
                  <th className="pb-2 font-medium text-right">耗时</th>
                </tr>
              </thead>
              <tbody>
                {recent.map((call, i) => (
                  <tr key={i} className="border-b border-border last:border-0">
                    <td className="py-2.5 text-[#8A8A8A]">
                      {call.timestamp ? new Date(call.timestamp).toLocaleString() : "-"}
                    </td>
                    <td className="py-2.5">
                      <Badge variant="outline" className="text-[10px]">{call.model || "unknown"}</Badge>
                    </td>
                    <td className="py-2.5 text-right">{call.tokens?.toLocaleString() ?? "-"}</td>
                    <td className="py-2.5 text-right">¥{(call.cost_yuan ?? 0).toFixed(4)}</td>
                    <td className="py-2.5 text-right text-[#8A8A8A]">{call.duration_ms ? `${call.duration_ms}ms` : "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
