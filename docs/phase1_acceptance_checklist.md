# 第一阶段验收清单

> 阶段名称：业务部门 MVP 闭环
> 验收日期：2026-07-06
> 版本：v1.5.0

## 一、已完成项

### 1. 业务页面

| 页面 | 生成 | 结构化展示 | 保存到 Delivery | 状态 |
|------|------|-----------|----------------|------|
| Marketing（7 种模式） | ✅ | ✅ | ✅ | 完成 |
| Image | ✅ | ✅ | ✅ | 完成 |
| Data | ✅ | ✅ | ✅ | 完成 |
| Research | ✅ | ✅ | ✅ | 完成 |
| Website | ✅ | ✅ | ✅ | 完成 |

### 2. 交付中心（MiniDelivery v1）

| 功能 | 状态 |
|------|------|
| 列表加载 | ✅ 完成 |
| 搜索（task_id） | ✅ 完成 |
| 预览（artifact.md） | ✅ 完成 |
| 详情页 | ✅ 完成 |
| 下载 | ✅ 完成 |
| agent_id 筛选 | ✅ 完成 |

### 3. 后端

| 项目 | 状态 |
|------|------|
| `/agents/{agent_id}/execute` 统一端点 | ✅ 完成 |
| MiniDelivery 字段映射（5 个业务 Agent） | ✅ 完成 |
| `/minidelivery` 路由注册 | ✅ 完成 |
| 搜索 None 防御 | ✅ 完成 |
| OUTPUT_ROOT 路径修复 | ✅ 完成 |

### 4. 前端

| 项目 | 状态 |
|------|------|
| Vite 代理 `/minidelivery` | ✅ 完成 |
| artifact 预览改用 `response.text()` | ✅ 完成 |
| Marketing 多模式展示 | ✅ 完成 |
| Delivery hooks 顺序修复 | ✅ 完成 |
| 首页卡片入口（5 个业务页） | ✅ 完成 |
| 侧边导航（6 个入口） | ✅ 完成 |

### 5. 文档

| 文档 | 状态 |
|------|------|
| 项目进度快照（2026-07-06） | ✅ 完成 |
| 用户使用说明 | ✅ 完成 |
| 验收清单（本文档） | ✅ 完成 |
| README 更新 | ✅ 完成 |

## 二、未进入项（明确排除）

| 项目 | 原因 |
|------|------|
| 真实图片生成 | 当前产出提示词框架，不接真实图片 API |
| 真实数据源 | 当前为模板/LLM 生成，不接真实数据库 |
| OpenClaw 联网调研 | 不在本阶段范围 |
| Boss 工作台功能扩展 | 保持现状 |
| Collaboration 协作 | 不在本阶段范围 |
| sandbox 沙箱 | 不在本阶段范围 |
| MiniDelivery v2 | v1 已冻结，不扩展 |
| Governance 接管业务 Agent | 普通业务 Agent 跳过 Governance Guard |

## 三、边界说明

### API 边界

- 业务页统一使用 `POST /agents/{agent_id}/execute`
- 旧端点 `POST /agents/{agent_id}/run` 仍存在但不推荐使用
- 本次收口未改变任何 API 接口定义

### 前端边界

- 不重构 UI 框架
- 不改路由结构
- 首页 6 个场景卡片中，Delivery 未单独成卡（通过侧边导航和"查看全部"进入）

### 后端边界

- 不改 MiniDelivery 数据结构
- 不改 Agent 执行逻辑
- 不改 Governance 策略

## 四、已知限制

| 限制 | 影响 | 缓解方案 |
|------|------|----------|
| 旧 `/run` 端点仍在代码中 | 可能误导开发者 | 文档标注为 legacy，不推荐使用 |
| 首页无 Delivery 卡片 | 用户可能找不到交付中心 | 侧边导航有入口，首页有"最近交付"widget |
| 无真实 LLM 调用时使用模板 fallback | 产出可能不够个性化 | 配置 API Key 后自动切换为 LLM 生成 |
| 中文终端乱码 | PowerShell 输出可能乱码 | artifact.md 文件本身为 UTF-8，不受影响 |

## 五、验证命令

```bash
# 后端导入验证
python -c "import backend.app; print('ok')"

# 前端构建验证
cd frontend-new && npm run build
```

## 六、结论

第一阶段"业务部门 MVP 闭环"功能已基本完成，综合完成度约 **95%**。

剩余 5% 为：
- 旧端点代码清理（不影响功能）
- 首页 Delivery 入口优化（不影响使用，侧边导航可达）

**可以标记第一阶段完成。**
