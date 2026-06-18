import { useState, useRef } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { BarChart3, Upload, Sparkles, Loader2, FileSpreadsheet, Check, AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { GlowCard } from "@/components/shared/glow-card"
import { Badge } from "@/components/ui/badge"

/* eslint-disable @typescript-eslint/no-explicit-any */

export default function DataPage() {
  const [file, setFile] = useState<File | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0]
    if (selectedFile) {
      setFile(selectedFile)
      setError(null)
      setResult(null)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    const droppedFile = e.dataTransfer.files[0]
    if (droppedFile) {
      setFile(droppedFile)
      setError(null)
      setResult(null)
    }
  }

  const handleUpload = async () => {
    if (!file) return

    setIsLoading(true)
    setError(null)
    setResult(null)

    try {
      const formData = new FormData()
      formData.append("file", file)

      const response = await fetch("/data/upload", {
        method: "POST",
        body: formData,
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || "上传失败")
      }

      const data = await response.json()
      setResult(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : "上传失败，请重试")
    } finally {
      setIsLoading(false)
    }
  }

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + " B"
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB"
    return (bytes / (1024 * 1024)).toFixed(1) + " MB"
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center">
          <BarChart3 className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">看数据</h1>
          <p className="text-muted-foreground">上传 Excel/CSV 文件，自动分析</p>
        </div>
      </div>

      {/* Upload Area */}
      <GlowCard>
        <h3 className="font-semibold mb-3">上传数据文件</h3>
        <div
          className={`border-2 border-dashed rounded-xl p-8 text-center transition-all cursor-pointer ${
            file
              ? "border-green/50 bg-green/5"
              : "border-border hover:border-primary/50 hover:bg-primary/5"
          }`}
          onClick={() => fileInputRef.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,.xlsx,.xls,.json,.tsv"
            onChange={handleFileSelect}
            className="hidden"
          />

          {file ? (
            <div className="flex flex-col items-center gap-2">
              <FileSpreadsheet className="w-10 h-10 text-green" />
              <p className="font-medium">{file.name}</p>
              <p className="text-sm text-muted-foreground">
                {formatFileSize(file.size)}
              </p>
              <Badge variant="success">已选择</Badge>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2">
              <Upload className="w-10 h-10 text-muted-foreground" />
              <p className="text-muted-foreground">
                点击选择文件，或拖拽文件到这里
              </p>
              <p className="text-xs text-muted-foreground">
                支持 Excel、CSV、JSON 格式
              </p>
            </div>
          )}
        </div>

        {file && (
          <Button
            onClick={handleUpload}
            disabled={isLoading}
            variant="glow"
            className="mt-4 w-full"
          >
            {isLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Sparkles className="w-4 h-4" />
            )}
            {isLoading ? "正在分析..." : "开始分析"}
          </Button>
        )}
      </GlowCard>

      {/* Error */}
      {error && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <GlowCard className="border-red-500/50">
            <div className="flex items-center gap-3">
              <AlertCircle className="w-5 h-5 text-red-500" />
              <p className="text-red-500">{error}</p>
            </div>
          </GlowCard>
        </motion.div>
      )}

      {/* Result */}
      <AnimatePresence>
        {result && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <GlowCard>
              <div className="flex items-center gap-2 mb-4">
                <Check className="w-5 h-5 text-green" />
                <h3 className="font-semibold">分析结果</h3>
              </div>

              <div className="space-y-4">
                {/* File Info */}
                <div className="p-3 rounded-lg bg-background border border-border">
                  <p className="text-sm">
                    <span className="text-muted-foreground">文件名：</span>
                    {result?.file_name as string}
                  </p>
                </div>

                {/* Data Summary */}
                {result?.explore?.data && (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <div className="p-3 rounded-lg bg-background border border-border text-center">
                      <p className="text-2xl font-bold text-primary">{(result.explore.data.rows as number) || 0}</p>
                      <p className="text-xs text-muted-foreground">行数</p>
                    </div>
                    <div className="p-3 rounded-lg bg-background border border-border text-center">
                      <p className="text-2xl font-bold text-cyan">{(result.explore.data.columns as number) || 0}</p>
                      <p className="text-xs text-muted-foreground">列数</p>
                    </div>
                    <div className="p-3 rounded-lg bg-background border border-border text-center">
                      <p className="text-2xl font-bold text-purple">{(result.explore.data.missing_cells as number) || 0}</p>
                      <p className="text-xs text-muted-foreground">缺失值</p>
                    </div>
                    <div className="p-3 rounded-lg bg-background border border-border text-center">
                      <p className="text-2xl font-bold text-green">{(result.explore.data.duplicate_rows as number) || 0}</p>
                      <p className="text-xs text-muted-foreground">重复行</p>
                    </div>
                  </div>
                )}

                {/* Column Info */}
                {result?.explore?.data?.column_names && (
                  <div>
                    <h4 className="text-sm font-medium mb-2">列名</h4>
                    <div className="flex flex-wrap gap-2">
                      {(result.explore.data.column_names as string[]).map((col: string, i: number) => (
                        <Badge key={i} variant="outline">
                          {col}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}

                {/* AI Analysis */}
                {result?.explore?.data?.ai_summary && (
                  <div>
                    <h4 className="text-sm font-medium mb-2">AI 分析</h4>
                    <div className="p-4 rounded-lg bg-background border border-border whitespace-pre-wrap text-sm">
                      {result.explore.data.ai_summary as string}
                    </div>
                  </div>
                )}
              </div>
            </GlowCard>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
