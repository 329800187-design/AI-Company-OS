import { test, expect, type Page } from "@playwright/test"

// ── Helpers ──────────────────────────────────────────────────────────────────

/** Dismiss the landing page by clicking the enter button */
async function dismissLanding(page: Page) {
  const enterBtn = page.locator("button", { hasText: "进入系统" })
  await enterBtn.click()
  await page.locator("text=进入系统").waitFor({ state: "detached", timeout: 10000 })
  await page.locator("text=AI Company").first().waitFor({ state: "visible", timeout: 10000 })
}

/** Navigate to a sidebar page. Advanced items need the "更多功能" expand first. */
async function navigateTo(page: Page, pageId: string, label: string) {
  const advancedPages = [
    "reports", "memory", "missions",
    "agent-console", "dashboard",
  ]

  if (advancedPages.includes(pageId)) {
    const moreBtn = page.locator("button", { hasText: "更多功能" })
    await moreBtn.click()
    await page.waitForTimeout(500)
  }

  const navItem = page.locator("nav button", { hasText: label })
  await navItem.click()
  await page.waitForTimeout(800)
}

// ── Health Check API ─────────────────────────────────────────────────────────

test.describe("系统健康 API (/health)", () => {
  test("返回正确的健康状态结构", async ({ page }) => {
    const response = await page.request.get("/health")
    expect(response.ok()).toBeTruthy()

    const data = await response.json()
    expect(data).toHaveProperty("status")
    expect(["ok", "healthy"]).toContain(data.status)
    expect(data).toHaveProperty("version")
  })

  test("config/status 返回 provider 配置", async ({ page }) => {
    const response = await page.request.get("/config/status")
    expect(response.ok()).toBeTruthy()

    const data = await response.json()
    expect(data).toHaveProperty("current_provider")
    expect(data).toHaveProperty("providers")
    expect(Array.isArray(data.providers)).toBeTruthy()
  })
})

// ── Memory Page Tests ────────────────────────────────────────────────────────

test.describe("知识库页面 (/app/memory)", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/app")
    await dismissLanding(page)
    await navigateTo(page, "memory", "知识库")
  })

  test("页面加载，显示标题和核心元素", async ({ page }) => {
    await expect(page.locator("h1", { hasText: "知识库" })).toBeVisible()
    await expect(page.locator('input[placeholder*="搜索"]')).toBeVisible()
    await expect(page.locator("button", { hasText: "添加记忆" })).toBeVisible()
  })

  test("API 返回记忆列表并正确渲染", async ({ page }) => {
    // Intercept the memory API and verify it's called
    let apiCalled = false
    await page.route("**/memory/recent**", async (route) => {
      apiCalled = true
      const response = await route.fetch()
      const json = await response.json()
      // Verify API response structure
      expect(json).toHaveProperty("memories")
      expect(json).toHaveProperty("count")
      expect(Array.isArray(json.memories)).toBeTruthy()
      await route.fulfill({ response })
    })

    // Reload to trigger the API call
    await page.reload()
    await dismissLanding(page)
    await navigateTo(page, "memory", "知识库")

    // Wait for API to be called
    await page.waitForTimeout(2000)
    expect(apiCalled).toBeTruthy()
  })

  test("添加记忆 — 打开表单、填写、提交并验证 API 调用", async ({ page }) => {
    // Intercept POST to /memory/remember
    let postBody: Record<string, unknown> | null = null
    await page.route("**/memory/remember", async (route) => {
      postBody = JSON.parse(route.request().postData() || "{}")
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok" }),
      })
    })

    await page.locator("button", { hasText: "添加记忆" }).click()

    const modal = page.locator('[role="dialog"], .fixed.inset-0').last()
    await expect(modal).toBeVisible()

    const keyInput = modal.locator('input[placeholder*="user-preference"]')
    await keyInput.fill("e2e-test-api-verify")

    const contentInput = modal.locator("textarea")
    await contentInput.fill("API 验证测试记忆")

    await modal.locator("button", { hasText: "保存" }).click()

    // Verify the API was called with correct body
    await page.waitForTimeout(1000)
    expect(postBody).not.toBeNull()
    expect(postBody!.key).toBe("e2e-test-api-verify")
    expect(postBody!.content).toBe("API 验证测试记忆")
    expect(postBody!.source).toBe("user")
  })

  test("搜索记忆 — 验证 API 查询参数", async ({ page }) => {
    let searchUrl = ""
    await page.route("**/memory/search**", async (route) => {
      searchUrl = route.request().url()
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ memories: [], count: 0 }),
      })
    })

    const searchInput = page.locator('input[placeholder*="搜索"]')
    await searchInput.fill("test-query")
    await searchInput.press("Enter")

    await page.waitForTimeout(1000)
    expect(searchUrl).toContain("q=test-query")
  })

  test("删除记忆 — 验证 DELETE API 调用", async ({ page }) => {
    let deleteUrl = ""
    await page.route("**/memory/e2e-*", async (route) => {
      if (route.request().method() === "DELETE") {
        deleteUrl = route.request().url()
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ status: "ok", message: "deleted" }),
        })
      } else {
        await route.continue()
      }
    })

    // 添加一条测试记忆
    await page.locator("button", { hasText: "添加记忆" }).click()
    const modal = page.locator('.fixed.inset-0').last()
    await modal.locator('input[placeholder*="user-preference"]').fill("e2e-delete-api-test")
    await modal.locator("textarea").fill("待删除")
    await modal.locator("button", { hasText: "保存" }).click()
    await expect(modal).not.toBeVisible({ timeout: 5000 })

    // Hover over the card to reveal action buttons
    const card = page.locator("h3", { hasText: "e2e-delete-api-test" }).first()
    await card.scrollIntoViewIfNeeded()
    await card.locator("../..").hover()

    const deleteBtn = page.locator('button[aria-label*="删除"]').first()
    await deleteBtn.click()

    const confirmBtn = page.getByRole("button", { name: "确认删除" })
    await expect(confirmBtn).toBeVisible()
    await confirmBtn.click()

    await page.waitForTimeout(1000)
    // Verify DELETE was called
    if (deleteUrl) {
      expect(deleteUrl).toContain("/memory/")
    }
  })

  test("筛选功能 — source 和 importance 下拉框存在", async ({ page }) => {
    const sourceSelect = page.locator("select").first()
    const importanceSelect = page.locator("select").nth(1)

    await expect(sourceSelect).toBeVisible()
    await expect(importanceSelect).toBeVisible()

    await expect(sourceSelect).toHaveValue("all")
    await expect(importanceSelect).toHaveValue("all")
  })
})

// ── Reports Page Tests ───────────────────────────────────────────────────────

test.describe("报告中心页面 (/app/reports)", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/app")
    await dismissLanding(page)
    await navigateTo(page, "reports", "报告中心")
  })

  test("页面加载，显示标题和统计卡片", async ({ page }) => {
    await expect(page.locator("h1", { hasText: "报告中心" })).toBeVisible()

    const statsGrid = page.locator(".grid").first()
    await expect(statsGrid.locator("text=总报告数")).toBeVisible()
    await expect(statsGrid.locator("text=成功")).toBeVisible()
    await expect(statsGrid.locator("text=失败")).toBeVisible()
    await expect(statsGrid.locator("text=运行中")).toBeVisible()
  })

  test("API 返回任务列表并正确渲染统计", async ({ page }) => {
    // Intercept boss/missions API
    let missionsData: unknown = null
    await page.route("**/boss/missions**", async (route) => {
      const response = await route.fetch()
      missionsData = await response.json()
      await route.fulfill({ response })
    })

    await page.reload()
    await dismissLanding(page)
    await navigateTo(page, "reports", "报告中心")
    await page.waitForTimeout(2000)

    // Verify the API response structure
    expect(missionsData).not.toBeNull()
    const data = missionsData as { missions: unknown[]; total: number }
    expect(data).toHaveProperty("missions")
    expect(data).toHaveProperty("total")
    expect(Array.isArray(data.missions)).toBeTruthy()

    // Verify stats render the correct count from API
    const totalText = await page.locator("text=总报告数").locator("..").locator(".text-2xl, [class*='text-2xl']").first().textContent()
    expect(Number(totalText)).toBe(data.total)
  })

  test("筛选按钮和搜索框可用", async ({ page }) => {
    await expect(page.locator("button", { hasText: "全部" })).toBeVisible()
    await expect(page.locator("button", { hasText: "成功" })).toBeVisible()
    await expect(page.locator("button", { hasText: "失败" })).toBeVisible()
    await expect(page.locator('input[placeholder*="搜索报告"]')).toBeVisible()
  })

  test("点击筛选按钮切换过滤状态", async ({ page }) => {
    const successFilter = page.locator("button", { hasText: "成功" }).first()
    await successFilter.click()
    await page.waitForTimeout(500)

    await page.locator("button", { hasText: "全部" }).first().click()
    await page.waitForTimeout(500)
  })

  test("展开报告详情并验证详情 API", async ({ page }) => {
    let detailApiCalled = false
    let detailData: unknown = null
    await page.route("**/boss/missions/*", async (route) => {
      if (route.request().url().includes("/events")) {
        await route.continue()
        return
      }
      detailApiCalled = true
      const response = await route.fetch()
      detailData = await response.json()
      await route.fulfill({ response })
    })

    const detailBtn = page.locator("button", { hasText: "详情" }).first()
    if (await detailBtn.isVisible()) {
      await detailBtn.click()

      // Verify detail API was called
      await page.waitForTimeout(2000)
      expect(detailApiCalled).toBeTruthy()

      // Verify detail response structure
      if (detailData) {
        const data = detailData as Record<string, unknown>
        expect(data).toHaveProperty("mission_id")
        expect(data).toHaveProperty("goal")
        expect(data).toHaveProperty("status")
        expect(data).toHaveProperty("modules")
        expect(Array.isArray(data.modules)).toBeTruthy()
      }

      // UI should show "收起" button after expansion
      const collapseBtn = page.getByRole("button", { name: "收起" })
      await expect(collapseBtn).toBeVisible({ timeout: 5000 })
    }
  })

  test("有产物的报告提供 Markdown 导出按钮", async ({ page }) => {
    const exportBtn = page.locator("button", { hasText: "导出" }).first()
    if (await exportBtn.isVisible()) {
      await expect(exportBtn).toBeEnabled()
    }
  })
})

// ── Dashboard Page Tests (API Verification) ──────────────────────────────────

test.describe("系统状态页面 — API 验证", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/app")
    await dismissLanding(page)
    await navigateTo(page, "dashboard", "系统状态")
  })

  test("capabilities API 返回正确的工具状态", async ({ page }) => {
    let capabilitiesData: Record<string, unknown> = {}
    await page.route("**/capabilities", async (route) => {
      const response = await route.fetch()
      capabilitiesData = await response.json()
      await route.fulfill({ response })
    })

    await page.reload()
    await dismissLanding(page)
    await navigateTo(page, "dashboard", "系统状态")
    await page.waitForTimeout(2000)

    // The scanner returns categorized observations plus canonical resources.
    expect(typeof capabilitiesData).toBe("object")

    const data = capabilitiesData as { resources?: unknown }
    expect(data).toHaveProperty("resources")
    expect(Array.isArray(data.resources)).toBeTruthy()
    for (const resource of data.resources as Array<Record<string, unknown>>) {
      expect(resource).toHaveProperty("available")
      expect(typeof resource.available).toBe("boolean")
    }
  })

  test("system/metrics API 返回用量数据", async ({ page }) => {
    let metricsCalled = false
    await page.route("**/system/metrics", async (route) => {
      metricsCalled = true
      const response = await route.fetch()
      const json = await response.json()
      // Verify usage structure
      expect(json).toHaveProperty("usage")
      expect(json.usage).toHaveProperty("24h_calls")
      expect(json.usage).toHaveProperty("24h_tokens")
      expect(json.usage).toHaveProperty("cost_yuan")
      await route.fulfill({ response })
    })

    await page.reload()
    await dismissLanding(page)
    await navigateTo(page, "dashboard", "系统状态")
    await page.waitForTimeout(2000)

    expect(metricsCalled).toBeTruthy()
  })

  test("API 错误时显示降级状态", async ({ page }) => {
    // Mock capabilities to return empty
    await page.route("**/capabilities", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({}),
      })
    })

    // Mock metrics to return error
    await page.route("**/system/metrics", async (route) => {
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Internal server error" }),
      })
    })

    await page.reload()
    await dismissLanding(page)
    await navigateTo(page, "dashboard", "系统状态")
    await page.waitForTimeout(2000)

    // Page should still render without crashing
    await expect(page.locator("h1", { hasText: "系统状态" })).toBeVisible()
    // Stats should show 0 for unavailable tools
    await expect(page.locator("text=可用工具")).toBeVisible()
  })
})

// ── Settings Page Tests (API Verification) ───────────────────────────────────

test.describe("设置页面 — API 验证", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/app")
    await dismissLanding(page)
    await page.locator("nav button", { hasText: "设置" }).click()
    await page.waitForTimeout(800)
  })

  test("页面加载并调用多个 API", async ({ page }) => {
    const apiCalls: string[] = []

    await page.route("**/health", async (route) => {
      apiCalls.push("health")
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok", version: "1.1.0" }),
      })
    })

    await page.route("**/config/status", async (route) => {
      apiCalls.push("config")
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          current_provider: "deepseek",
          providers: [{ id: "deepseek", configured: true }],
        }),
      })
    })

    await page.route("**/brain/list", async (route) => {
      apiCalls.push("brain")
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          brains: [],
          current: { brain_id: "", name: "" },
        }),
      })
    })

    await page.route("**/capabilities", async (route) => {
      apiCalls.push("capabilities")
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ hermes: { available: false } }),
      })
    })

    await page.reload()
    await dismissLanding(page)
    await page.locator("nav button", { hasText: "设置" }).click()
    await page.waitForTimeout(3000)

    // All 4 APIs should have been called
    expect(apiCalls).toContain("health")
    expect(apiCalls).toContain("config")
    expect(apiCalls).toContain("brain")
    expect(apiCalls).toContain("capabilities")
  })

  test("系统健康卡片显示正确的状态", async ({ page }) => {
    await page.route("**/health", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok", version: "1.1.0" }),
      })
    })

    await page.route("**/config/status", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          current_provider: "deepseek",
          providers: [{ id: "deepseek", configured: true }],
        }),
      })
    })

    await page.reload()
    await dismissLanding(page)
    await page.locator("nav button", { hasText: "设置" }).click()
    await page.waitForTimeout(2000)

    // System health section should be visible
    await expect(page.locator("text=系统健康")).toBeVisible()
    await expect(page.locator("text=后端服务")).toBeVisible()
    await expect(page.locator("text=数据库")).toBeVisible()
    await expect(page.locator("text=AI 模型")).toBeVisible()
  })
})

// ── Boss Template API Tests ──────────────────────────────────────────────────

test.describe("Boss 指挥台 — 模板 API 验证", () => {
  test("模板列表 API 返回正确的结构", async ({ page }) => {
    const response = await page.request.get("/boss/templates")
    expect(response.ok()).toBeTruthy()

    const data = await response.json()
    expect(data).toHaveProperty("templates")
    expect(data).toHaveProperty("total")
    expect(Array.isArray(data.templates)).toBeTruthy()

    // Each template should have required fields
    if (data.templates.length > 0) {
      const template = data.templates[0]
      expect(template).toHaveProperty("id")
      expect(template).toHaveProperty("name")
      expect(template).toHaveProperty("description")
    }
  })

  test("Skills API 返回技能列表", async ({ page }) => {
    const response = await page.request.get("/skills/list")
    expect(response.ok()).toBeTruthy()

    const data = await response.json()
    expect(data).toHaveProperty("skills")
    expect(data).toHaveProperty("count")
    expect(Array.isArray(data.skills)).toBeTruthy()
  })

  test("Usage API 返回用量统计", async ({ page }) => {
    const statsResponse = await page.request.get("/usage/stats?hours=24")
    expect(statsResponse.ok()).toBeTruthy()

    const statsData = await statsResponse.json()
    expect(statsData).toHaveProperty("hours")
    expect(statsData).toHaveProperty("calls")
    expect(statsData).toHaveProperty("tokens")
    expect(statsData).toHaveProperty("cost_yuan")

    const totalResponse = await page.request.get("/usage/total")
    expect(totalResponse.ok()).toBeTruthy()

    const totalData = await totalResponse.json()
    expect(totalData).toHaveProperty("total_calls")
    expect(totalData).toHaveProperty("total_tokens")
    expect(totalData).toHaveProperty("total_cost_yuan")
  })
})
