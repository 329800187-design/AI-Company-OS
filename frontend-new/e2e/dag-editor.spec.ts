import { test, expect, type APIRequestContext, type Page } from "@playwright/test"

// ── Helpers ──────────────────────────────────────────────────────────────────

/** Navigate directly to boss page (skip landing via ?page=boss) */
async function goToBoss(page: Page) {
  await page.goto("/app?page=boss")
  await page.waitForTimeout(1500)
}

/** Open the create template form */
async function openCreateForm(page: Page) {
  await page.locator("button", { hasText: "创建模板" }).click()
  await page.waitForTimeout(300)
}

/** Fill the template name field */
async function fillTemplateName(page: Page, name: string) {
  // The name input is in the template form area, not inside DagEditor
  const nameInput = page.locator('input[placeholder="模板名称"]')
  await nameInput.clear()
  await nameInput.fill(name)
}

async function createTemplateFixture(request: APIRequestContext, name: string) {
  const response = await request.post("/boss/graph/templates", {
    data: {
      name,
      description: "Playwright DAG editor fixture",
      goal_hint: "验证 DAG 编辑器",
      nodes: [
        { id: "research", agent_id: "research", title: "市场调研", prompt: "调研市场" },
        { id: "marketing", agent_id: "marketing", title: "营销方案", prompt: "生成营销方案" },
      ],
      edges: [{ from_node: "research", to_node: "marketing", handoff_type: "context" }],
    },
  })
  expect(response.ok()).toBeTruthy()
  const body = await response.json()
  return body.template.template_id as string
}

async function deleteTemplateFixture(request: APIRequestContext, templateId: string | null) {
  if (!templateId) return
  const response = await request.delete(`/boss/graph/templates/${templateId}`)
  expect(response.ok()).toBeTruthy()
}

/** Add a node via DagEditor "添加节点" button */
async function addNode(page: Page) {
  await page.locator("button", { hasText: "添加节点" }).click()
  await page.waitForTimeout(200)
}

/** Add an edge via DagEditor "添加边" button */
async function addEdge(page: Page) {
  await page.locator("button", { hasText: "添加边" }).click()
  await page.waitForTimeout(200)
}

/** Expand node card at index (click header to toggle) */
async function expandNode(page: Page, index: number) {
  const nodeSection = page.locator('h5', { hasText: '节点 / Nodes' }).locator('..')
  const nodeCards = nodeSection.locator('[class*="space-y"]').locator('> div')
  await nodeCards.nth(index).locator('[class*="select-none"]').click()
  await page.waitForTimeout(200)
}

/** Fill node field in expanded card */
async function fillNodeField(page: Page, nodeIndex: number, field: string, value: string) {
  const nodeSection = page.locator('h5', { hasText: '节点 / Nodes' }).locator('..')
  const nodeCards = nodeSection.locator('[class*="space-y"]').locator('> div')
  const card = nodeCards.nth(nodeIndex)
  const input = card.locator(`input[placeholder="${field}"], textarea[placeholder="${field}"]`)
  await input.clear()
  await input.fill(value)
}

// ── Tests ────────────────────────────────────────────────────────────────────

test.describe("DAG 编辑器 — 创建模板", () => {
  let createdTemplateId: string | null = null

  test.beforeEach(async ({ page }) => {
    await goToBoss(page)
  })

  test.afterEach(async ({ request }) => {
    await deleteTemplateFixture(request, createdTemplateId)
    createdTemplateId = null
  })

  test("打开创建表单，显示 DagEditor", async ({ page }) => {
    await openCreateForm(page)

    // DagEditor should be visible
    await expect(page.getByRole("heading", { name: "DAG 编辑器", exact: true })).toBeVisible()
    await expect(page.locator("button", { hasText: "添加节点" })).toBeVisible()
    await expect(page.locator("button", { hasText: "添加边" })).toBeVisible()

    // Default draft should have 2 nodes pre-populated
    await expect(page.locator("text=2 节点")).toBeVisible()
    await expect(page.locator("text=1 边")).toBeVisible()
  })

  test("创建 3 节点模板，wave 预览实时更新", async ({ page, request }) => {
    const templateName = `E2E DAG ${Date.now()}`
    await openCreateForm(page)

    // The default draft has research -> marketing. Add a third node.
    await addNode(page)

    // Expand the third node and fill fields
    await expandNode(page, 2)
    await fillNodeField(page, 2, "node_id", "image")
    await fillNodeField(page, 2, "agent_id", "image")
    await fillNodeField(page, 2, "节点标题", "视觉方案")

    // Wave preview should now show 3 nodes
    await expect(page.getByText("3 节点", { exact: true }).first()).toBeVisible()

    // Add edge: marketing -> image
    await addEdge(page)
    await page.waitForTimeout(200)

    // Expand the edge and select nodes from dropdowns
    const edgeCards = page.locator('h5', { hasText: '边 / Edges' }).locator('..').locator('[class*="space-y"]').locator('> div')
    const edgeSection = edgeCards.nth(1)
    await edgeSection.locator('[class*="select-none"]').click()
    await page.waitForTimeout(200)

    // Select from_node = marketing, to_node = image
    const selects = edgeSection.locator('select')
    await selects.nth(0).selectOption("marketing")
    await selects.nth(1).selectOption("image")

    // Should show 2 edges now
    await expect(page.getByText("2 边", { exact: true }).first()).toBeVisible()

    // Fill template name
    await fillTemplateName(page, templateName)

    // Save
    await page.locator("button", { hasText: "保存模板" }).click()
    await page.waitForTimeout(1500)

    // Should appear in template list
    await expect(page.getByText(templateName, { exact: true })).toBeVisible({ timeout: 10000 })

    const listResponse = await request.get("/boss/graph/templates")
    expect(listResponse.ok()).toBeTruthy()
    const listBody = await listResponse.json()
    createdTemplateId = listBody.templates.find((template: { name: string }) => template.name === templateName)?.template_id ?? null
    expect(createdTemplateId).not.toBeNull()
  })
})

test.describe("DAG 编辑器 — 编辑与克隆", () => {
  let templateId: string | null = null

  test.beforeEach(async ({ page, request }, testInfo) => {
    templateId = await createTemplateFixture(request, `E2E ${testInfo.title} ${Date.now()}`)
    await goToBoss(page)
  })

  test.afterEach(async ({ request }) => {
    await deleteTemplateFixture(request, templateId)
    templateId = null
  })

  test("编辑已有模板，数据正确回填", async ({ page }) => {
    // Wait for templates to load
    await page.waitForTimeout(2000)

    // Find a template card and click "编辑"
    const editBtn = page.locator("button", { hasText: "编辑" }).first()
    await expect(editBtn).toBeVisible()
    await editBtn.click()
    await page.waitForTimeout(500)

    // DagEditor should be visible with data
    await expect(page.getByRole("heading", { name: "DAG 编辑器", exact: true })).toBeVisible()

    // The form should have name filled
    const nameInput = page.locator('input[placeholder="模板名称"]')
    const nameValue = await nameInput.inputValue()
    expect(nameValue.length).toBeGreaterThan(0)

    // Should show node count > 0
    const nodeBadge = page.getByText(/\d+ 节点/, { exact: true }).first()
    await expect(nodeBadge).toBeVisible()
  })

  test("克隆模板，名称带「副本」后缀", async ({ page }) => {
    await page.waitForTimeout(2000)

    const cloneBtn = page.locator("button", { hasText: "克隆" }).first()
    await expect(cloneBtn).toBeVisible()
    await cloneBtn.click()
    await page.waitForTimeout(500)

    // Name should end with "副本"
    const nameInput = page.locator('input[placeholder="模板名称"]')
    const nameValue = await nameInput.inputValue()
    expect(nameValue).toContain("副本")

    // DagEditor should be visible
    await expect(page.getByRole("heading", { name: "DAG 编辑器", exact: true })).toBeVisible()
  })
})

test.describe("DAG 编辑器 — 校验拦截", () => {
  test.beforeEach(async ({ page }) => {
    await goToBoss(page)
    await openCreateForm(page)
  })

  test("自环边被前端拦截", async ({ page }) => {
    // The default has research -> marketing edge. Expand it and set both to research.
    const edgeSection = page.locator('h5', { hasText: '边 / Edges' }).locator('..').locator('[class*="space-y"]').locator('> div').first()
    await edgeSection.locator('[class*="select-none"]').click()
    await page.waitForTimeout(200)

    const selects = edgeSection.locator('select')
    await selects.nth(0).selectOption("research")
    await selects.nth(1).selectOption("research")

    // Should show self-loop error
    await expect(page.locator("text=自环")).toBeVisible({ timeout: 3000 })
  })

  test("重复节点 ID 被前端拦截", async ({ page }) => {
    // Add a second node with same ID as first
    await addNode(page)
    await expandNode(page, 2)
    await fillNodeField(page, 2, "node_id", "research")  // same as first node
    await fillNodeField(page, 2, "agent_id", "research")

    // Should show duplicate ID error
    await expect(page.locator("text=重复")).toBeVisible({ timeout: 3000 })
  })

  test("缺失节点引用被前端拦截", async ({ page }) => {
    const edgeSection = page.locator('h5', { hasText: '边 / Edges' }).locator('..').locator('[class*="space-y"]').locator('> div').first()
    await edgeSection.locator('[class*="select-none"]').click()
    const fromSelect = edgeSection.locator("select").first()
    await fromSelect.evaluate((select) => {
      const option = document.createElement("option")
      option.value = "missing-node"
      option.textContent = "missing-node"
      select.appendChild(option)
    })
    await fromSelect.selectOption("missing-node")

    await expect(page.locator('text=不存在')).toBeVisible({ timeout: 3000 })
  })

  test("循环被前端拦截", async ({ page }) => {
    // Set up: A -> B -> C -> A (cycle)
    // Clear default and start fresh by adding nodes
    // The default has research -> marketing. Add a third node and create a cycle.

    // Add third node
    await addNode(page)
    await expandNode(page, 2)
    await fillNodeField(page, 2, "node_id", "website")
    await fillNodeField(page, 2, "agent_id", "website")

    // Add second edge: marketing -> website
    await addEdge(page)
    const edgeCards2 = page.locator('h5', { hasText: '边 / Edges' }).locator('..').locator('[class*="space-y"]').locator('> div')
    const edge2 = edgeCards2.nth(1)
    await edge2.locator('[class*="select-none"]').click()
    await page.waitForTimeout(200)
    const selects2 = edge2.locator('select')
    await selects2.nth(0).selectOption("marketing")
    await selects2.nth(1).selectOption("website")

    // Add third edge: website -> research (creates cycle)
    await addEdge(page)
    const edgeCards3 = page.locator('h5', { hasText: '边 / Edges' }).locator('..').locator('[class*="space-y"]').locator('> div')
    const edge3 = edgeCards3.nth(2)
    await edge3.locator('[class*="select-none"]').click()
    await page.waitForTimeout(200)
    const selects3 = edge3.locator('select')
    await selects3.nth(0).selectOption("website")
    await selects3.nth(1).selectOption("research")

    // Should show cycle error
    await expect(page.locator("text=循环")).toBeVisible({ timeout: 3000 })
  })
})

test.describe("DAG 编辑器 — 删除节点自动清理边", () => {
  test.beforeEach(async ({ page }) => {
    await goToBoss(page)
    await openCreateForm(page)
  })

  test("删除节点后关联边自动移除", async ({ page }) => {
    // Default: 2 nodes (research, marketing), 1 edge (research -> marketing)
    await expect(page.locator("text=2 节点")).toBeVisible()
    await expect(page.locator("text=1 边")).toBeVisible()

    // Accept the confirm dialog (added in Phase 6.3)
    page.on("dialog", (dialog) => dialog.accept())

    // Delete the first node (research) - click the trash icon in the node header
    const nodeSection = page.locator('h5', { hasText: '节点 / Nodes' }).locator('..').locator('[class*="space-y"]').locator('> div').first()
    await nodeSection.locator('button:has(svg)').last().click()  // trash button
    await page.waitForTimeout(300)

    // Should now have 1 node and 0 edges (edge referenced "research")
    await expect(page.locator("text=1 节点")).toBeVisible()
    await expect(page.locator("text=0 边")).toBeVisible()
  })
})

test.describe("DAG 编辑器 — agent_id 下拉建议", () => {
  test.beforeEach(async ({ page }) => {
    await goToBoss(page)
    await openCreateForm(page)
  })

  test("agent_id 输入框支持 datalist 建议", async ({ page }) => {
    // Expand first node
    await expandNode(page, 0)

    // The agent_id input should have a datalist attribute
    const nodeSection = page.locator('h5', { hasText: '节点 / Nodes' }).locator('..').locator('[class*="space-y"]').locator('> div').first()
    const agentInput = nodeSection.locator('input[list="dag-common-agents"]')
    await expect(agentInput).toBeVisible()

    // The datalist should exist in the DOM
    const datalist = page.locator('datalist#dag-common-agents')
    await expect(datalist).toHaveCount(1)

    // It should have 5 options
    const options = datalist.locator('option')
    await expect(options).toHaveCount(5)
  })
})

test.describe("DAG 编辑器 — from/to 下拉选择", () => {
  test.beforeEach(async ({ page }) => {
    await goToBoss(page)
    await openCreateForm(page)
  })

  test("from_node/to_node 使用 select 下拉，选项来自已有节点", async ({ page }) => {
    // Expand the first edge
    const edgeSection = page.locator('h5', { hasText: '边 / Edges' }).locator('..').locator('[class*="space-y"]').locator('> div').first()
    await edgeSection.locator('[class*="select-none"]').click()
    await page.waitForTimeout(200)

    // Should have 2 select elements (from_node, to_node)
    const selects = edgeSection.locator('select')
    await expect(selects).toHaveCount(2)  // from_node + to_node (handoff_type is still text input)

    // Each select should have "-- 选择节点 --" placeholder + 2 node options
    const fromOptions = selects.nth(0).locator('option')
    await expect(fromOptions).toHaveCount(3)  // placeholder + research + marketing

    // Verify the options contain the node IDs
    const optionTexts = await fromOptions.allTextContents()
    expect(optionTexts).toContain("-- 选择节点 --")
    expect(optionTexts).toContain("research")
    expect(optionTexts).toContain("marketing")
  })
})

// ── Undo / Redo & Edit Safety ──────────────────────────────

test.describe("DAG 编辑器 — 撤销/重做与编辑安全", () => {
  test.beforeEach(async ({ page }) => {
    await goToBoss(page)
    await openCreateForm(page)
  })

  test("撤销：添加节点后撤销，回到 2 节点", async ({ page }) => {
    await expect(page.locator("text=2 节点")).toBeVisible()

    await addNode(page)
    await expect(page.locator("text=3 节点")).toBeVisible()

    // Click undo button
    await page.locator('[data-testid="undo-btn"]').click()
    await page.waitForTimeout(200)

    await expect(page.locator("text=2 节点")).toBeVisible()
  })

  test("重做：添加 → 撤销 → 重做，回到 3 节点", async ({ page }) => {
    await addNode(page)
    await expect(page.locator("text=3 节点")).toBeVisible()

    await page.locator('[data-testid="undo-btn"]').click()
    await page.waitForTimeout(200)
    await expect(page.locator("text=2 节点")).toBeVisible()

    await page.locator('[data-testid="redo-btn"]').click()
    await page.waitForTimeout(200)
    await expect(page.locator("text=3 节点")).toBeVisible()
  })

  test("重命名节点 ID 自动同步关联边", async ({ page }) => {
    // Default: research -> marketing edge
    // Expand first node (research) and rename to "research2"
    // Use fill() directly (not clear+fill) so the onChange gets oldId="research" properly
    await expandNode(page, 0)
    await page.locator('[data-testid="node-id-input-0"]').fill("research2")
    await page.waitForTimeout(300)

    // Verify edge header shows "research2→marketing" (not "research→marketing")
    const edgeHeader = page.locator('h5', { hasText: '边 / Edges' }).locator('..').locator('[class*="space-y"]').locator('> div').first().locator('[class*="font-mono"]')
    await expect(edgeHeader).toContainText("research2")

    // No validation errors about missing node
    await expect(page.locator("text=不存在")).not.toBeVisible()
  })

  test("清空后重新输入 ID 仍会同步关联边", async ({ page }) => {
    await expandNode(page, 0)
    const input = page.locator('[data-testid="node-id-input-0"]')
    await input.clear()
    await input.fill("research2")
    await page.waitForTimeout(300)

    const edgeHeader = page.locator('h5', { hasText: '边 / Edges' }).locator('..').locator('[class*="space-y"]').locator('> div').first().locator('[class*="font-mono"]')
    await expect(edgeHeader).toContainText("research2")
    await expect(page.locator("text=不存在")).not.toBeVisible()
  })

  test("重复 ID 的逐字输入不会污染关联边", async ({ page }) => {
    await expandNode(page, 0)
    const input = page.locator('[data-testid="node-id-input-0"]')
    await input.press("Control+A")
    await input.type("marketing")
    await page.waitForTimeout(300)

    const edgeHeader = page.locator('h5', { hasText: '边 / Edges' }).locator('..').locator('[class*="space-y"]').locator('> div').first().locator('[class*="font-mono"]')
    await expect(edgeHeader).toContainText("research")
    await expect(edgeHeader).not.toContainText("marketin→")
    await expect(page.locator("text=重复")).toBeVisible()
  })

  test("删除节点 — 确认后节点和关联边被移除", async ({ page }) => {
    // Default: 2 nodes, 1 edge
    await expect(page.locator("text=2 节点")).toBeVisible()
    await expect(page.locator("text=1 边")).toBeVisible()

    // Accept the confirm dialog
    page.on("dialog", (dialog) => dialog.accept())

    const nodeSection = page.locator('h5', { hasText: '节点 / Nodes' }).locator('..').locator('[class*="space-y"]').locator('> div').first()
    await nodeSection.locator('button:has(svg)').last().click()
    await page.waitForTimeout(300)

    await expect(page.locator("text=1 节点")).toBeVisible()
    await expect(page.locator("text=0 边")).toBeVisible()
  })

  test("删除节点 — 取消后数据不变", async ({ page }) => {
    await expect(page.locator("text=2 节点")).toBeVisible()
    await expect(page.locator("text=1 边")).toBeVisible()

    // Dismiss the confirm dialog
    page.on("dialog", (dialog) => dialog.dismiss())

    const nodeSection = page.locator('h5', { hasText: '节点 / Nodes' }).locator('..').locator('[class*="space-y"]').locator('> div').first()
    await nodeSection.locator('button:has(svg)').last().click()
    await page.waitForTimeout(300)

    // Data should be unchanged
    await expect(page.locator("text=2 节点")).toBeVisible()
    await expect(page.locator("text=1 边")).toBeVisible()
  })
})
