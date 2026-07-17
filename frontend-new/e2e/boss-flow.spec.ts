import { test, expect, type Page } from "@playwright/test"

// ── Helpers ──────────────────────────────────────────────────────────────────

const MISSION_ID = "mission_e2e_test_01"

async function goToBossCommandCenter(page: Page) {
  await page.goto("/app?page=boss")
  await expect(page.getByText("今天要推进什么业务目标？")).toBeVisible({ timeout: 15000 })
  await page.getByRole("button", { name: "指挥台", exact: true }).click()
  await page.waitForTimeout(300)
}

// ── Mock Data ────────────────────────────────────────────────────────────────

function makeModule(id: string, title: string, status: string, result = "") {
  return {
    module_id: id, title, status, prompt: "请分析：测试目标", result,
    confidence: status === "done" ? 0.85 : 0,
    warnings: status === "partial" ? ["部分数据缺失"] : [],
    error: status === "failed" ? "执行失败" : "",
    used_tools: [], mode: "local",
    started_at: status !== "pending" ? "2026-07-13T12:00:00" : null,
    finished_at: ["done", "partial"].includes(status) ? "2026-07-13T12:01:00" : null,
    duration_ms: status === "done" ? 5000 : 0,
    next_actions: status === "done" ? ["下一步建议"] : [],
    structured_output: {},
  }
}

function makeMission(status: string, mod: Record<string, string> = {}) {
  const s = (k: string) => mod[k] || (status === "pending_review" ? "pending" : status === "running" ? "pending" : "done")
  const strat = mod.strategy || (status === "pending_review" ? "pending" : status === "running" ? "running" : "done")
  return {
    mission_id: MISSION_ID, goal: "测试 E2E 目标", status,
    created_at: "2026-07-13T12:00:00", updated_at: "2026-07-13T12:00:00",
    modules: [
      makeModule("strategy", "战略摘要", strat, strat === "done" ? "战略分析结果内容充足" : ""),
      makeModule("market", "市场与竞品", s("market"), s("market") === "done" ? "市场分析结果内容充足" : s("market") === "partial" ? "部分市场分析结果" : ""),
      makeModule("marketing", "营销方案", s("marketing"), s("marketing") === "done" ? "营销方案结果内容充足" : ""),
      makeModule("landing", "落地页草稿", "skipped"),
      makeModule("actions", "执行清单", s("actions"), s("actions") === "done" ? "执行清单结果内容充足" : ""),
    ],
    metrics: {
      total_modules: 5,
      succeeded_modules: ["ready_for_review", "done"].includes(status) ? 4 : 0,
      failed_modules: 0, skipped_modules: 1, interrupted_modules: 0,
      duration_ms: ["ready_for_review", "done"].includes(status) ? 20000 : 0,
      warning_count: 0, next_action_count: 0,
      completion_rate: ["ready_for_review", "done"].includes(status) ? 1.0 : 0,
    },
  }
}

function makeEvents(status: string) {
  const evts = [
    { id: 1, mission_id: MISSION_ID, type: "mission_created", module_id: null, message: "创建任务", payload: {}, created_at: "2026-07-13T12:00:00" },
  ]
  if (status !== "pending_review") {
    evts.push({ id: 2, mission_id: MISSION_ID, type: "mission_started", module_id: null, message: "开始执行任务", payload: {}, created_at: "2026-07-13T12:00:01" })
  }
  if (["ready_for_review", "done"].includes(status)) {
    evts.push({ id: 3, mission_id: MISSION_ID, type: "mission_ready", module_id: null, message: "所有模块执行完成，等待人工审核", payload: {}, created_at: "2026-07-13T12:00:10" })
  }
  return { mission_id: MISSION_ID, events: evts, total: evts.length }
}

// ── Tests ────────────────────────────────────────────────────────────────────

test.describe("Boss Command Center 主链路", () => {
  test("创建计划 → pending_review + 模块列表 + 确认执行按钮", async ({ page }) => {
    page.route(/\/boss\/missions/, async (route) => {
      const url = route.request().url()
      const method = route.request().method()
      if (method === "POST" && /\/boss\/missions$/.test(url)) {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(makeMission("pending_review")) })
      } else if (method === "GET" && !/\/(events|run|accept)$/.test(url)) {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(makeMission("pending_review")) })
      } else if (/\/events$/.test(url)) {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(makeEvents("pending_review")) })
      } else {
        await route.continue()
      }
    })

    await goToBossCommandCenter(page)
    await page.locator('[data-testid="boss-goal-input"]').fill("测试 E2E 目标")
    await page.locator('[data-testid="boss-create-plan-btn"]').click()

    await expect(page.locator('[data-testid="boss-status-banner"]')).toBeVisible({ timeout: 5000 })
    await expect(page.getByText("计划已生成，等待确认执行").first()).toBeVisible({ timeout: 5000 })
    await expect(page.getByText("战略摘要").first()).toBeVisible()
    await expect(page.locator('[data-testid="boss-confirm-run-btn"]')).toBeVisible()
    await expect(page.getByText("用户已确认完成")).not.toBeVisible()
  })

  test("确认执行 → running → ready_for_review + 结果 + 接受按钮", async ({ page }) => {
    let pollCount = 0
    let runResolved = false

    page.route(/\/boss\/missions/, async (route) => {
      const url = route.request().url()
      const method = route.request().method()

      // POST create
      if (method === "POST" && /\/boss\/missions$/.test(url)) {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(makeMission("pending_review")) })
        return
      }
      // POST run — delay 3s so polling has time to fire
      if (method === "POST" && /\/run$/.test(url)) {
        await new Promise(r => setTimeout(r, 3000))
        runResolved = true
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(makeMission("running", { strategy: "running" })) })
        return
      }
      // GET events
      if (/\/events$/.test(url)) {
        const status = pollCount <= 3 ? "running" : "ready_for_review"
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(makeEvents(status)) })
        return
      }
      // GET mission detail
      if (method === "GET") {
        pollCount++
        const status = pollCount <= 3 ? "running" : "ready_for_review"
        const mods = pollCount <= 3 ? { strategy: "running" } : {}
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(makeMission(status, mods)) })
        return
      }
      await route.continue()
    })

    await goToBossCommandCenter(page)
    await page.locator('[data-testid="boss-goal-input"]').fill("测试 E2E 目标")
    await page.locator('[data-testid="boss-create-plan-btn"]').click()
    await expect(page.locator('[data-testid="boss-confirm-run-btn"]')).toBeVisible({ timeout: 5000 })
    await page.locator('[data-testid="boss-confirm-run-btn"]').click()

    // Wait for polling to advance to ready_for_review (pollCount > 3)
    await expect(page.getByText("已生成结果，等待人工审核")).toBeVisible({ timeout: 15000 })
    await expect(page.getByText("战略分析结果内容充足").first()).toBeVisible()
    await expect(page.locator('[data-testid="boss-accept-btn"]')).toBeVisible()
  })

  test("接受结果 → done + 按钮消失", async ({ page }) => {
    let pollCount = 0

    page.route(/\/boss\/missions/, async (route) => {
      const url = route.request().url()
      const method = route.request().method()

      if (method === "POST" && /\/boss\/missions$/.test(url)) {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(makeMission("pending_review")) })
        return
      }
      if (method === "POST" && /\/run$/.test(url)) {
        await new Promise(r => setTimeout(r, 3000))
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(makeMission("running", { strategy: "running" })) })
        return
      }
      if (method === "POST" && /\/accept$/.test(url)) {
        pollCount = 100
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(makeMission("done")) })
        return
      }
      if (/\/events$/.test(url)) {
        const status = pollCount <= 3 ? "running" : pollCount <= 6 ? "ready_for_review" : "done"
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(makeEvents(status)) })
        return
      }
      if (method === "GET") {
        pollCount++
        const status = pollCount <= 3 ? "running" : pollCount <= 6 ? "ready_for_review" : "done"
        const mods = pollCount <= 3 ? { strategy: "running" } : {}
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(makeMission(status, mods)) })
        return
      }
      await route.continue()
    })

    await goToBossCommandCenter(page)
    await page.locator('[data-testid="boss-goal-input"]').fill("测试 E2E 目标")
    await page.locator('[data-testid="boss-create-plan-btn"]').click()
    await expect(page.locator('[data-testid="boss-confirm-run-btn"]')).toBeVisible({ timeout: 5000 })
    await page.locator('[data-testid="boss-confirm-run-btn"]').click()
    await expect(page.getByText("已生成结果，等待人工审核")).toBeVisible({ timeout: 15000 })

    await page.locator('[data-testid="boss-accept-btn"]').click()
    await expect(page.getByText("用户已确认完成")).toBeVisible({ timeout: 5000 })
    await expect(page.locator('[data-testid="boss-accept-btn"]')).not.toBeVisible()
  })

  test("partial 状态显示已有结果 + 重跑按钮", async ({ page }) => {
    page.route(/\/boss\/missions/, async (route) => {
      const url = route.request().url()
      const method = route.request().method()

      if (method === "POST" && /\/boss\/missions$/.test(url)) {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(makeMission("pending_review")) })
        return
      }
      if (method === "POST" && /\/run$/.test(url)) {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(makeMission("partial", { strategy: "done", market: "partial", marketing: "failed", actions: "done" })) })
        return
      }
      if (/\/events$/.test(url)) {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(makeEvents("ready_for_review")) })
        return
      }
      if (method === "GET") {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(makeMission("partial", { strategy: "done", market: "partial", marketing: "failed", actions: "done" })) })
        return
      }
      await route.continue()
    })

    await goToBossCommandCenter(page)
    await page.locator('[data-testid="boss-goal-input"]').fill("测试 E2E 目标")
    await page.locator('[data-testid="boss-create-plan-btn"]').click()
    await expect(page.locator('[data-testid="boss-confirm-run-btn"]')).toBeVisible({ timeout: 5000 })
    await page.locator('[data-testid="boss-confirm-run-btn"]').click()

    await expect(page.getByText("部分模块有结果，等待人工处理")).toBeVisible({ timeout: 10000 })
    await expect(page.getByText("战略分析结果内容充足").first()).toBeVisible()
    await expect(page.locator('[data-testid="boss-accept-btn"]')).toBeVisible()
    await expect(page.getByRole("button", { name: "重新执行", exact: true })).toBeVisible()
  })

  test("runMission 失败保留 partial 结果", async ({ page }) => {
    page.route(/\/boss\/missions/, async (route) => {
      const url = route.request().url()
      const method = route.request().method()

      if (method === "POST" && /\/boss\/missions$/.test(url)) {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(makeMission("pending_review")) })
        return
      }
      if (method === "POST" && /\/run$/.test(url)) {
        await route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "内部服务器错误" }) })
        return
      }
      if (/\/events$/.test(url)) {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(makeEvents("ready_for_review")) })
        return
      }
      if (method === "GET") {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(makeMission("partial", { strategy: "done", market: "failed", marketing: "failed", actions: "failed" })) })
        return
      }
      await route.continue()
    })

    await goToBossCommandCenter(page)
    await page.locator('[data-testid="boss-goal-input"]').fill("测试 E2E 目标")
    await page.locator('[data-testid="boss-create-plan-btn"]').click()
    await expect(page.locator('[data-testid="boss-confirm-run-btn"]')).toBeVisible({ timeout: 5000 })
    await page.locator('[data-testid="boss-confirm-run-btn"]').click()

    await expect(page.getByText("操作失败").first()).toBeVisible({ timeout: 5000 })
    await expect(page.getByText("战略分析结果内容充足").first()).toBeVisible()
  })
})

// ── Phase 6.24: 旧草稿缓存清理 ─────────────────────────────────────────────

test.describe("Boss 页面旧草稿缓存清理", () => {
  const OLD_DRAFT_KEY = "boss_graph_template_draft_v1"
  const NEW_DRAFT_KEY = "boss_graph_template_draft_v2"

  const oldDraftWithBannedTerm = JSON.stringify({
    name: "旧模板",
    description: "旧描述",
    goal_hint: "旧目标",
    nodes: [
      { id: "research", agent_id: "research", task_type: "research_brief", title: "上下文调研", prompt: "调研相关内容" },
      { id: "marketing", agent_id: "marketing", task_type: "copywriting", title: "沟通方案", prompt: "设计沟通策略" },
    ],
    edges: [
      { from_node: "research", to_node: "marketing", handoff_type: "context" },
    ],
  })

  test("旧 v1 草稿不恢复、不显示'上下文调研'", async ({ page }) => {
    // 预置旧 v1 草稿到 localStorage
    await page.addInitScript(([key, value]) => {
      localStorage.setItem(key, value)
    }, [OLD_DRAFT_KEY, oldDraftWithBannedTerm])

    await page.goto("/app?page=boss")
    await expect(page.getByText("今天要推进什么业务目标？")).toBeVisible({ timeout: 15000 })

    // 旧草稿恢复弹窗不应出现
    await page.waitForTimeout(1000)
    await expect(page.getByText("发现未保存草稿")).not.toBeVisible()

    // "上下文调研" 不应出现在页面可见文本中
    const bodyText = await page.locator("body").innerText()
    expect(bodyText).not.toContain("上下文调研")

    // v1 key 应已被清理
    const v1Value = await page.evaluate((key) => localStorage.getItem(key), OLD_DRAFT_KEY)
    expect(v1Value).toBeNull()
  })

  test("v2 草稿正常恢复", async ({ page }) => {
    const v2Draft = JSON.stringify({
      name: "新模板",
      description: "新描述",
      goal_hint: "新目标",
      nodes: [
        { id: "research", agent_id: "research", task_type: "research_brief", title: "上下文整理", prompt: "整理相关内容" },
        { id: "marketing", agent_id: "marketing", task_type: "copywriting", title: "沟通方案", prompt: "设计沟通策略" },
      ],
      edges: [
        { from_node: "research", to_node: "marketing", handoff_type: "context" },
      ],
    })

    await page.addInitScript(([key, value]) => {
      localStorage.setItem(key, value)
    }, [NEW_DRAFT_KEY, v2Draft])

    await page.goto("/app?page=boss")
    await expect(page.getByText("今天要推进什么业务目标？")).toBeVisible({ timeout: 15000 })

    // v2 草稿恢复弹窗应出现
    await expect(page.getByText("发现未保存草稿")).toBeVisible({ timeout: 5000 })
    await expect(page.getByText("新模板")).toBeVisible()
  })
})
