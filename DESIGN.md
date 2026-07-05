# AI Company OS — UI 设计规范

> 后续修改前端 UI 时**必须优先遵守本文件**。

---

## 产品定位

AI 公司操作系统 — 多智能体协作指挥台。面向创业者/运营者，帮助他们通过 AI Agent 完成市场分析、营销策划、落地页生成和执行清单。

## 设计风格

- **专业** — 数据密集但不杂乱，信息层级清晰
- **清爽** — 大量留白，低饱和色调，不花哨
- **未来感** — 微妙的渐变和光效，但克制使用
- **高效** — 操作路径短，状态一目了然

## 适用场景

| 场景 | 页面 | 重点 |
|------|------|------|
| Boss 指挥台 | `/boss` | 目标输入 → 模块执行 → 结果展示 |
| Agent 控制台 | `/agents` | 单个 Agent 任务执行 |
| 任务流 | `/tasks` | 任务列表和状态跟踪 |
| 数据报告 | `/reports` | 图表和数据可视化 |

## 技术栈

- React 18 + TypeScript
- Tailwind CSS + shadcn/ui 组件库
- Framer Motion 动画
- Lucide React 图标

---

## 颜色系统

### 基础色（Tailwind semantic tokens）

| Token | 用途 | 浅色模式 | 深色模式 |
|-------|------|----------|----------|
| `background` | 页面背景 | `hsl(0 0% 100%)` | `hsl(222.2 84% 4.9%)` |
| `foreground` | 主文本 | `hsl(222.2 84% 4.9%)` | `hsl(210 40% 98%)` |
| `card` | 卡片背景 | `hsl(0 0% 100%)` | `hsl(222.2 84% 4.9%)` |
| `muted` | 次要文本/禁用 | `hsl(210 40% 96%)` | `hsl(217.2 32.6% 17.5%)` |
| `border` | 边框 | `hsl(214.3 31.8% 91.4%)` | `hsl(217.2 32.6% 17.5%)` |
| `primary` | 主操作/强调 | `hsl(222.2 47.4% 11.2%)` | `hsl(210 40% 98%)` |

### 语义色

| 状态 | 颜色 | 用途 |
|------|------|------|
| 成功 `success` | `hsl(142 76% 36%)` | 完成、通过 |
| 警告 `warning` | `hsl(38 92% 50%)` | 需注意、需授权 |
| 错误 `destructive` | `hsl(0 84% 60%)` | 失败、错误 |
| 信息 `info` | `hsl(217 91% 60%)` | 进行中、提示 |

### 渐变（克制使用）

- 主渐变：`from-primary to-cyan` — 仅用于页面标题图标背景
- 光效卡片：`GlowCard` 组件统一处理，不要手动添加渐变

---

## 卡片规范

- 使用 `<GlowCard>` 组件（`@/components/shared/glow-card`）
- 圆角：`rounded-xl`（12px）
- 边框：`border border-border`
- 内边距：`p-4` 或 `p-6`
- 背景：`bg-card/70` 或 `bg-background/60`（半透明层叠效果）
- 悬停：`hover:border-primary/30 hover:bg-accent/50`
- **不要**给卡片加 box-shadow，用边框 + 背景色区分层级

---

## 按钮规范

### 变体

| 变体 | 用途 | 样式 |
|------|------|------|
| `variant="glow"` | 主操作（生成、执行） | 渐变背景 + 光效 |
| `variant="default"` | 次要操作 | 实色背景 |
| `variant="outline"` | 辅助操作（导出、历史） | 透明背景 + 边框 |
| `variant="ghost"` | 最低强调 | 无边框 |
| `variant="destructive"` | 危险操作 | 红色 |

### 尺寸

| 尺寸 | 用途 |
|------|------|
| `size="lg"` | 页面主按钮 |
| `size="default"` | 普通操作 |
| `size="sm"` | 行内/工具栏按钮 |
| `size="icon"` | 图标按钮 |

### 图标 + 文字

所有带文字的按钮都用 `className="gap-1"` 或 `className="gap-2"` 保持图标和文字间距一致。

---

## 间距系统

- 基础单位：4px
- 组件内部：`gap-1`（4px）、`gap-2`（8px）、`gap-3`（12px）
- 卡片之间：`gap-4`（16px）、`gap-6`（24px）
- 区域之间：`space-y-6`（24px）
- 页面边距：容器自动居中，无额外 padding

---

## 字体层级

| 层级 | 样式 | 用途 |
|------|------|------|
| Display | `text-2xl font-bold` | 页面标题 |
| Heading | `text-xl font-semibold` | 模块标题 |
| Subheading | `text-base font-medium` | 卡片标题 |
| Body | `text-sm` | 正文内容 |
| Caption | `text-xs text-muted-foreground` | 辅助说明、时间戳 |
| Label | `text-xs font-medium` | 标签、Badge |

---

## 状态提示

### Badge 变体

| 状态 | Badge | 文案 |
|------|-------|------|
| 待执行 | `<Badge variant="secondary">` | "待执行" |
| 进行中 | `<Badge variant="info">` | "执行中" |
| 已完成 | `<Badge variant="success">` | "已完成" |
| 需处理 | `<Badge variant="destructive">` | "需处理" |
| 需授权 | `<Badge variant="warning">` | "需授权" |
| 已跳过 | `<Badge variant="secondary">` | "已跳过" |

### 图标对应

| 状态 | 图标 | 颜色 |
|------|------|------|
| 待执行 | `<Icon>` (模块默认图标) | `text-primary` |
| 进行中 | `<Loader2 className="animate-spin">` | `text-primary` |
| 已完成 | `<CheckCircle2>` | `text-green` |
| 失败 | `<AlertCircle>` | `text-yellow` |
| 需授权 | `<ShieldOff>` | `text-orange-500` |
| 已跳过 | `<SkipForward>` | `text-muted-foreground` |

---

## 空状态

- 使用虚线边框容器：`border-dashed border-border bg-background/40`
- 居中布局：`flex min-h-[360px] flex-col items-center justify-center`
- 大图标：`h-10 w-10 text-muted-foreground`
- 标题：`font-medium`
- 说明：`mt-2 max-w-sm text-sm text-muted-foreground`

---

## 加载状态

- 全局加载：`<Loader2 className="h-4 w-4 animate-spin" />` 在按钮内
- 区域加载：居中大图标 + "正在生成..." 文案
- 骨架屏：暂不使用，用 loading 状态 + 文案代替

---

## 错误状态

- 黄色警告框：`border border-yellow/20 bg-yellow/10 p-4`
- 红色错误框：`border border-destructive/20 bg-destructive/10 p-4`
- 图标：`<AlertCircle className="h-5 w-5 text-yellow">`
- 错误文案直接展示，不要只显示 "出错了"

---

## 授权状态（浏览器自动化）

- 橙色警告框：`border border-orange-300 bg-orange-50`
- 图标：`<ShieldOff className="h-5 w-5 text-orange-500">`
- 标题："需要授权浏览器采集"
- 操作按钮：`<Shield>` 图标 + "授权并重试本模块"

---

## 动画规范

- 页面切换：framer-motion `initial={{ opacity: 0, y: 10 }}` → `animate={{ opacity: 1, y: 0 }}`
- 时长：`transition={{ duration: 0.2 }}`
- 模块结果区：使用 `key={activeModule}` 触发切换动画
- **不要**给列表项加 stagger 动画（太慢）
- **不要**使用 `scale` 动画（会抖动）

---

## 图标规范

- 图标库：Lucide React
- 模块图标映射：
  - strategy → `<Target>`
  - market → `<Search>`
  - marketing → `<Megaphone>`
  - landing → `<Globe2>`
  - actions → `<ClipboardList>`
- 操作图标：
  - 执行 → `<Play>`
  - 重试 → `<RotateCcw>`
  - 导出 → `<Download>`
  - 历史 → `<History>`
  - 授权 → `<Shield>` / `<ShieldOff>`
  - 模板 → `<Sparkles>`

---

## 禁止事项

1. **不要**使用内联样式（`style={{}}`），全部用 Tailwind 类名
2. **不要**硬编码颜色值（如 `#fff`、`gray-200`），用 semantic tokens
3. **不要**给卡片加 `box-shadow`
4. **不要**使用 `transition: all`
5. **不要**在同一个页面混用多种圆角值
6. **不要**为了单一用途创建新组件，先检查现有组件
7. **不要**在按钮中只放图标不加 tooltip（`size="icon"` 除外）
