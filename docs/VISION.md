# AI Company OS · 大汉式组织架构设计稿

> 版本：2.0  
> 日期：2026-07-03  
> 状态：项目主目标文档，替代旧版“终极架构设计文档”  
> 用途：指导后续所有功能设计、代码修改、模块归位和 Claude 执行任务。

---

## 0. 一句话定义

**AI Company OS 是一个“大汉式 AI 公司操作系统”：用户从任意业务入口提交目标，系统像一个朝廷/集团一样完成任务受理、部门分派、Agent 执行、风控审计、产物交付和战报归档。**

它不是一个单独的 Boss 工作台，也不是一个单独的 Agent 调用器，而是一套：

```text
多业务入口
→ 统一任务单
→ 中枢调度
→ Agent 百官将相执行
→ Governance 御史风控
→ MiniDelivery 萧何后勤交付
→ Timeline 功劳簿记录
→ Boss 工作台总览
```

---

## 1. 总设计原则

### 1.1 Boss 不是系统本体

Boss 工作台只是高层入口，相当于皇帝办公室/董事长办公室。

它可以：

- 下达战略目标
- 查看各部门战报
- 审批高风险行动
- 观察项目全局状态

它不应该：

- 吞掉所有业务入口
- 代替营销、图片、数据、研究等业务页面
- 直接承担所有产出逻辑
- 成为系统唯一主链路

### 1.2 Agent 是真正产出者

系统的生产力来自 Agent，而不是来自 Governance、MiniDelivery 或 Boss 页面。

业务页面应该优先调用对应业务 Agent：

- Marketing Agent 负责营销文案、活动方案、社媒内容
- Image Agent 负责图片提示词、图片生成、视觉产出
- Data Agent 负责数据分析、表格解读、结论汇总
- Research Agent 负责调研、竞品分析、市场洞察
- Website Agent 负责落地页、网站结构、页面文案
- Code/Browser/CLI Agent 负责代码、浏览器、命令行等高风险执行

### 1.3 Governance 是御史廷尉，不是生产部门

Governance 负责：

- 风险判断
- 人工确认
- 沙箱要求
- 审计记录
- 阻断危险动作

Governance 不负责：

- 默认生成营销内容
- 默认生成图片内容
- 默认生成数据报告
- 替代业务 Agent 做生产

如果 Governance 参与产出，只能作为历史兼容或兜底路径，不能作为长期主链路。

### 1.4 MiniDelivery 是萧何后勤，不是创意部门

MiniDelivery 负责：

- 保存产物
- 生成交付包
- 提供预览/下载
- 记录版本
- 形成可复用成果

MiniDelivery 不负责：

- 判断业务应该怎么做
- 替代 Agent 生成核心内容
- 把交付流程变成生产流程

### 1.5 Collaboration 是相府军令，不是普通任务入口

Collaboration 负责复杂任务：

- 多步骤拆解
- 多 Agent 协同
- 长流程推进
- 人工确认节点
- 项目级战报

普通单业务任务不应该强行进入 Collaboration。

例如：

- “写一条小红书文案” → Marketing Agent
- “分析这份表格” → Data Agent
- “生成一套项目方案，包含调研、营销、落地页、图片素材” → Collaboration

---

## 2. 大汉式系统组织架构

```text
AI Company OS
├─ 长安中枢 Core OS
│  ├─ 任务受理
│  ├─ 任务分类
│  ├─ Agent 选择
│  ├─ 风险预判
│  └─ 执行记录
│
├─ Boss 工作台
│  ├─ 高层总览
│  ├─ 战略目标输入
│  ├─ 各部门战报
│  └─ 高风险审批
│
├─ 业务前台
│  ├─ 营销部 Marketing
│  ├─ 图片部 Image
│  ├─ 数据部 Data
│  ├─ 研究部 Research
│  ├─ 网站部 Website
│  └─ 模板部 Templates
│
├─ 相府 / 项目管理 Collaboration
│  ├─ 复杂任务拆解
│  ├─ 多 Agent 编排
│  ├─ 步骤状态跟踪
│  └─ 项目战报输出
│
├─ 将军府 / Agent 执行层
│  ├─ Marketing Agent
│  ├─ Image Agent
│  ├─ Data Agent
│  ├─ Research Agent
│  ├─ Website Agent
│  └─ Code/Browser/CLI Agent
│
├─ 萧何后勤 / MiniDelivery
│  ├─ 产物保存
│  ├─ 交付包生成
│  ├─ 下载预览
│  └─ 版本归档
│
├─ 廷尉御史 / Governance
│  ├─ 风险判断
│  ├─ 人工审批
│  ├─ 沙箱要求
│  └─ 审计日志
│
├─ 吏部 / Agent Registry
│  ├─ Agent 花名册
│  ├─ 能力说明
│  ├─ 风险等级
│  └─ 输入输出规范
│
└─ 太史令 / Timeline & KPI
   ├─ 执行记录
   ├─ 成败统计
   ├─ Agent 绩效
   └─ 项目历史
```

---

## 3. 模块职责对照表

| 大汉机构 | 系统模块 | 主要职责 | 明确不能做 |
|---|---|---|---|
| 长安中枢 | Core OS / Execution Layer | 任务受理、分类、路由、状态记录 | 直接替所有 Agent 产出 |
| 皇帝办公室 | Boss 工作台 | 总览、战略、审批、跨部门指挥 | 成为唯一入口 |
| 各业务衙门 | Marketing/Image/Data/Research/Website Pages | 用户办事入口、展示业务结果 | 混用无关业务链路 |
| 将军府/百官 | Agents | 真正执行和产出 | 把结果做成随意格式 |
| 相府军令 | Collaboration | 复杂任务拆解和多 Agent 协同 | 承接所有普通任务 |
| 御史廷尉 | Governance/Risk Gate | 风控、审批、审计、沙箱 | 作为默认生产者 |
| 萧何后勤 | MiniDelivery | 保存、预览、下载、归档 | 决定业务内容 |
| 吏部 | Agent Registry/Discovery | 能力登记、风险等级、调用方式 | 执行业务任务 |
| 太史令 | Timeline/KPI | 记录过程、战报、绩效 | 影响业务产出判断 |

---

## 4. 标准主链路

所有业务入口最终应该共享同一套底层秩序。

```text
用户从任意入口提交目标
→ 生成统一任务单 TaskRequest
→ 判断任务类型与来源入口
→ 查 Agent Registry 选择执行者
→ Governance 做必要风险判断
→ 单 Agent 或 Collaboration 执行
→ Agent 返回统一结果 ExecutionResult
→ MiniDelivery 保存 artifacts
→ 前端展示 summary / structured_output / artifacts
→ Timeline 记录战报
→ Boss 工作台可查看汇总
```

关键判断：

```text
简单单部门任务 → 直接调用单 Agent
复杂多步骤任务 → 进入 Collaboration
高风险任务 → Governance 审批或沙箱
产物型任务 → MiniDelivery 归档
管理层查看 → Boss 工作台读取战报
```

---

## 5. 统一任务单 TaskRequest

所有入口都应该逐步收敛到统一任务单。

```json
{
  "goal": "用户想完成的目标",
  "source": "marketing | image | data | research | website | boss | collaboration | api",
  "task_type": "copywriting | image_generation | data_analysis | market_research | website_draft | multi_agent_project",
  "preferred_agent": "marketing | image | data | research | website | auto",
  "context": {
    "platform": "xiaohongshu",
    "audience": "optional",
    "business_info": "optional"
  },
  "input": {
    "raw_text": "optional",
    "files": [],
    "urls": []
  },
  "expected_output": {
    "format": "structured_json | markdown | artifact_pack",
    "needs_artifact": true
  },
  "risk_preference": {
    "allow_browser": false,
    "allow_code_execution": false,
    "allow_http": false
  }
}
```

第一阶段不要求所有页面立刻完全迁移，但新代码必须向这个结构靠拢。

---

## 6. 统一结果格式 ExecutionResult

所有 Agent 和执行链路最终都应返回统一结果。

```json
{
  "ok": true,
  "mode": "single_agent | collaboration | deterministic_pipeline | fallback",
  "agent_id": "marketing",
  "task_type": "copywriting",
  "summary": "本次产出的简要说明",
  "structured_output": {
    "headline": "optional",
    "body": "optional",
    "cta": "optional"
  },
  "artifacts": [
    {
      "id": "artifact_id",
      "type": "markdown | json | image | html | zip",
      "title": "交付物标题",
      "path": "optional",
      "preview": "optional"
    }
  ],
  "warnings": [],
  "errors": [],
  "next_actions": [
    "可以继续优化标题",
    "可以生成配图提示词"
  ],
  "risk_decision": {
    "risk_level": "low | medium | high",
    "recommended_action": "allow | confirm | review_required | sandbox_required"
  },
  "timeline_events": []
}
```

最低要求：

- 前端不能只显示一段不可控文本。
- Agent 不能各自返回完全不同的结构。
- fallback 必须显式展示，不能静默吞掉失败。
- warnings/errors 必须被前端看见。

---

## 7. 三条旧路线的新归位

过去项目里出现过三条路线：

```text
1. Agent 工作台 / 业务产出路线
2. Governance / Core 底层路线
3. Boss / Workflow / Pipeline 路线
```

新设计不是三条路线竞争，而是统一归位：

### 7.1 Agent 业务产出路线

归位为：

```text
各业务衙门 + 将军府 Agent 执行层
```

它是系统生产主力。

重点包括：

- Marketing
- Image
- Data
- Research
- Website
- Templates

### 7.2 Governance/Core 底层路线

归位为：

```text
长安中枢 + 廷尉御史
```

它负责制度、秩序、风险、审计。

它不是默认生产者。

### 7.3 Boss/Workflow/Pipeline 路线

归位为：

```text
Boss 工作台 + 相府 Collaboration + Timeline 战报
```

它负责管理视角、复杂项目和过程记录。

它不能吞掉所有业务入口。

---

## 8. 前端入口设计

前端不是一个页面，而是一组业务衙门。

```text
/boss          高层总览与战略入口
/marketing     营销产出入口
/image         图片/视觉产出入口
/data          数据分析入口
/research      市场/竞品调研入口
/website       网站/落地页入口
/templates     模板化产出入口
/collaboration 多 Agent 项目入口
/delivery      交付物中心
/governance    风控/审计中心
```

每个业务页面应该做到：

- 用户输入目标
- 调用对应 Agent 或统一执行层
- 展示结构化结果
- 明确展示 fallback/错误/警告
- 能把结果保存到交付中心
- 能继续发起下一步动作

---

## 9. 后端边界设计

### 9.1 Agent Router

职责：

- 执行单个 Agent
- 返回统一结果
- 保持向后兼容

不负责：

- 多步骤项目管理
- 审批流
- 产物长期归档

### 9.2 Execution Layer

职责：

- 接收统一 TaskRequest
- 判断单 Agent / Collaboration / fallback
- 包装统一 ExecutionResult
- 对接 Governance 与 MiniDelivery

注意：

- 如果当前系统还没有成熟 Execution Layer，可以先从文档和 Marketing 样板开始。
- 不要为了“统一”立刻制造第四套混乱入口。

### 9.3 Governance Router

职责：

- classify
- risk gate
- confirm/review/sandbox decision
- audit log

不应该长期承担默认业务产出。

### 9.4 Collaboration Router

职责：

- 创建复杂计划
- 推进步骤
- 处理人工确认
- 处理 sandbox_required 流程
- 记录项目 timeline

### 9.5 MiniDelivery Router

职责：

- 保存 artifacts
- 查询交付物
- 预览/下载
- 管理交付包

---

## 10. 当前阶段优先级

### 第一阶段：定章程与盘点

目标：

- 本文档成为主设计稿。
- 盘点现有前端入口、后端接口、Agent 输出和交付路径。
- 标记职责错位位置。

不要做：

- 大重构
- 删除旧 API
- 把 Boss 变成唯一入口
- 继续让 Governance 承担默认生产

### 第二阶段：打通一个样板业务链路

优先选择 Marketing，因为它已经最接近 Agent-first。

目标链路：

```text
Marketing 页面
→ TaskRequest
→ Marketing Agent
→ ExecutionResult
→ 前端结构化展示
→ MiniDelivery 可保存
→ Timeline 可记录
```

### 第三阶段：迁移其他业务入口

按顺序：

```text
Image
→ Data
→ Research
→ Website
→ Templates
```

每迁移一个页面，只做一件事：

```text
让该业务页面稳定调用对应 Agent，并展示统一结果。
```

### 第四阶段：强化交付中心

MiniDelivery 需要逐步变成真正交付系统：

- 产物列表
- 产物预览
- 产物下载
- 版本历史
- 关联来源任务
- 关联执行 Agent

### 第五阶段：强化 Collaboration

只在单 Agent 解决不了时进入 Collaboration。

它应该处理：

- 多 Agent 项目
- 多步骤计划
- 中途人工确认
- 风险审批
- 失败重试
- 最终项目交付包

### 第六阶段：Boss 工作台总览化

Boss 工作台最终应该看到：

- 今日任务
- 各部门产出
- 高风险审批
- Agent 绩效
- 交付物汇总
- 项目进度

Boss 不应该亲自承担所有业务页面的功能。

---

## 11. 不允许继续跑偏的点

后续开发必须避免：

- 为了炫酷继续堆 Boss 页面
- 让 Governance 继续当生产入口
- 让 MiniDelivery 参与业务判断
- 所有任务都强行走 Collaboration
- Agent 输出没有统一结构
- 前端只显示一坨文本
- fallback 静默发生
- 测试只保护框架，不保护真实用户链路
- 新增一套入口却不处理旧入口关系

---

## 12. Claude 修改系统时的工作规则

给 Claude 的修改任务必须符合以下顺序：

```text
1. 先读 docs/VISION.md
2. 先盘点当前链路
3. 先确认模块职责
4. 再做最小修改
5. 每次只修一个业务链路
6. 保留旧 API，逐步迁移
7. 添加或更新测试
8. 最后汇报修改文件、链路变化和未处理问题
```

Claude 每次输出必须包含：

- 修改了哪些文件
- 修复了哪个链路
- 是否改变了 API
- 是否改变了前端调用
- 是否影响 Governance / Collaboration / MiniDelivery
- 跑了哪些测试
- 哪些问题留到下一阶段

---

## 13. 第一条正式执行指令

后续第一轮 Claude 任务建议使用：

```text
请先阅读 docs/VISION.md。

当前项目目标已经调整为“大汉式 AI Company OS”：

- Boss 工作台只是高层入口，不是系统唯一入口。
- 业务页面是各业务衙门。
- Agent 是真正产出者。
- Governance 只做风控、审批、审计。
- MiniDelivery 只做产物保存、预览、下载、归档。
- Collaboration 只处理复杂多 Agent 项目。
- 所有入口逐步共享统一 TaskRequest 和 ExecutionResult。

本轮不要大重构，不要删除旧 API，不要提交 Git。

请先做只读盘点：

1. 扫描 frontend-new/src/pages 下所有业务页面。
2. 列出每个页面调用 api/client.ts 的哪个方法。
3. 对应到 backend/routers 的哪个 endpoint。
4. 判断该链路是真 Agent 产出、Governance 产出、MiniDelivery 产出，还是旧 Boss/Workflow 产出。
5. 找出职责错位的位置。
6. 找出最适合第一阶段修成样板链路的页面。
7. 输出下一步最小修改方案。

要求最后输出：

A. 当前真实链路图
B. 每个前端入口对应的后端接口
C. 每个后端接口对应的职责归位
D. 职责错位清单
E. 第一阶段建议修改文件
F. 不建议现在修改的内容
G. 需要新增或调整的测试
```

---

## 14. 最终判断

AI Company OS 的核心不是某一个页面，而是一套公司式执行秩序。

最终形态应该是：

```text
用户从任意业务入口下达目标
→ 系统形成任务单
→ 中枢判断该找谁
→ Agent 像百官将相一样执行
→ 御史系统管风险
→ 后勤系统管交付
→ 太史系统记战报
→ Boss 工作台看全局
```

这就是后续所有系统修改的主方向。
