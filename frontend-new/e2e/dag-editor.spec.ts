import { test, expect, type APIRequestContext, type Page } from "@playwright/test"
import { readFileSync } from "node:fs"

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

    // Click delete → React ConfirmDialog appears
    const nodeSection = page.locator('h5', { hasText: '节点 / Nodes' }).locator('..').locator('[class*="space-y"]').locator('> div').first()
    await nodeSection.locator('button:has(svg)').last().click()
    await page.waitForTimeout(300)

    // Confirm in the React dialog
    await page.locator('[data-testid="confirm-dialog-confirm"]').click()
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
    await expandNode(page, 0)
    await page.locator('[data-testid="node-id-input-0"]').fill("research2")
    // blur triggers edge sync
    await page.locator('[data-testid="node-id-input-0"]').blur()
    await page.waitForTimeout(300)

    // Verify edge header shows "research2→marketing" (not "research→marketing")
    const edgeHeader = page.locator('h5', { hasText: '边 / Edges' }).locator('..').locator('[class*="space-y"]').locator('> div').first().locator('[class*="font-mono"]')
    await expect(edgeHeader).toContainText("research2")

    // No validation errors about missing node
    await expect(page.locator("text=不存在")).not.toBeVisible()

    await page.locator('[data-testid="undo-btn"]').click()
    await expect(page.locator('[data-testid="node-id-input-0"]')).toHaveValue("research")
    await expect(edgeHeader).toContainText("research")
  })

  test("清空后重新输入 ID 仍会同步关联边", async ({ page }) => {
    await expandNode(page, 0)
    const input = page.locator('[data-testid="node-id-input-0"]')
    // Select all then type replacement (not clear+fill, which triggers two onChange calls)
    await input.click({ clickCount: 3 })
    await input.pressSequentially("research2", { delay: 30 })
    await input.blur()
    await page.waitForTimeout(300)

    const edgeHeader = page.locator('h5', { hasText: '边 / Edges' }).locator('..').locator('[class*="space-y"]').locator('> div').first().locator('[class*="font-mono"]')
    await expect(edgeHeader).toContainText("research2")
    await expect(page.locator("text=不存在")).not.toBeVisible()
  })

  test("重复 ID 的逐字输入不会污染关联边", async ({ page }) => {
    await expandNode(page, 0)
    const input = page.locator('[data-testid="node-id-input-0"]')
    // Select all then type duplicate ID (selects all first so oldId is "research")
    await input.click({ clickCount: 3 })
    await input.pressSequentially("marketing", { delay: 30 })
    await input.blur()
    await page.waitForTimeout(300)

    const edgeHeader = page.locator('h5', { hasText: '边 / Edges' }).locator('..').locator('[class*="space-y"]').locator('> div').first().locator('[class*="font-mono"]')
    // Edge should still show "research" (not synced because "marketing" is duplicate)
    await expect(edgeHeader).toContainText("research")
    await expect(page.locator("text=重复")).toBeVisible()
  })

  test("删除节点 — 确认后节点和关联边被移除", async ({ page }) => {
    // Default: 2 nodes, 1 edge
    await expect(page.locator("text=2 节点")).toBeVisible()
    await expect(page.locator("text=1 边")).toBeVisible()

    // Click delete button → dialog appears
    const nodeSection = page.locator('h5', { hasText: '节点 / Nodes' }).locator('..').locator('[class*="space-y"]').locator('> div').first()
    await nodeSection.locator('button:has(svg)').last().click()
    await page.waitForTimeout(300)

    // Confirm dialog should appear
    await expect(page.locator('[data-testid="confirm-dialog"]')).toBeVisible()

    // Click confirm button
    await page.locator('[data-testid="confirm-dialog-confirm"]').click()
    await page.waitForTimeout(300)

    await expect(page.locator("text=1 节点")).toBeVisible()
    await expect(page.locator("text=0 边")).toBeVisible()
  })

  test("删除节点 — 取消后数据不变", async ({ page }) => {
    await expect(page.locator("text=2 节点")).toBeVisible()
    await expect(page.locator("text=1 边")).toBeVisible()

    // Click delete button → dialog appears
    const nodeSection = page.locator('h5', { hasText: '节点 / Nodes' }).locator('..').locator('[class*="space-y"]').locator('> div').first()
    await nodeSection.locator('button:has(svg)').last().click()
    await page.waitForTimeout(300)

    // Click cancel button
    await page.locator('[data-testid="confirm-dialog-cancel"]').click()
    await page.waitForTimeout(300)

    // Data should be unchanged
    await expect(page.locator("text=2 节点")).toBeVisible()
    await expect(page.locator("text=1 边")).toBeVisible()
  })

  test("删除对话框 — Esc 关闭，数据不变", async ({ page }) => {
    await expect(page.locator("text=2 节点")).toBeVisible()

    // Click delete button
    const nodeSection = page.locator('h5', { hasText: '节点 / Nodes' }).locator('..').locator('[class*="space-y"]').locator('> div').first()
    const deleteButton = nodeSection.locator('button:has(svg)').last()
    await deleteButton.click()
    await page.waitForTimeout(300)

    // Dialog should be visible
    await expect(page.locator('[data-testid="confirm-dialog"]')).toBeVisible()
    await expect(page.locator('[data-testid="confirm-dialog-cancel"]')).toBeFocused()
    await page.keyboard.press("Shift+Tab")
    await expect(page.locator('[data-testid="confirm-dialog-confirm"]')).toBeFocused()

    // Press Esc to close
    await page.keyboard.press("Escape")
    await page.waitForTimeout(300)

    // Dialog should be gone, data unchanged
    await expect(page.locator('[data-testid="confirm-dialog"]')).not.toBeVisible()
    await expect(page.locator("text=2 节点")).toBeVisible()
    await expect(page.locator("text=1 边")).toBeVisible()
    await expect(deleteButton).toBeFocused()
  })

  test("删除对话框 — 显示节点名称和关联边数", async ({ page }) => {
    // Click delete on first node (research, has 1 edge)
    const nodeSection = page.locator('h5', { hasText: '节点 / Nodes' }).locator('..').locator('[class*="space-y"]').locator('> div').first()
    await nodeSection.locator('button:has(svg)').last().click()
    await page.waitForTimeout(300)

    // Dialog should show node name and edge count
    const dialog = page.locator('[data-testid="confirm-dialog"]')
    await expect(dialog).toBeVisible()
    await expect(dialog.locator('text=市场调研')).toBeVisible()
    await expect(dialog.locator('text=research')).toBeVisible()
    await expect(dialog.locator('text=1 条边')).toBeVisible()

    // Cancel to close
    await page.locator('[data-testid="confirm-dialog-cancel"]').click()
  })

  test("删除后可撤销恢复", async ({ page }) => {
    await expect(page.locator("text=2 节点")).toBeVisible()
    await expect(page.locator("text=1 边")).toBeVisible()

    // Delete first node (confirm dialog)
    const nodeSection = page.locator('h5', { hasText: '节点 / Nodes' }).locator('..').locator('[class*="space-y"]').locator('> div').first()
    await nodeSection.locator('button:has(svg)').last().click()
    await page.waitForTimeout(300)
    await page.locator('[data-testid="confirm-dialog-confirm"]').click()
    await page.waitForTimeout(300)

    // Verify deletion
    await expect(page.locator("text=1 节点")).toBeVisible()
    await expect(page.locator("text=0 边")).toBeVisible()

    // Undo → restore
    await page.locator('[data-testid="undo-btn"]').click()
    await page.waitForTimeout(300)

    // Should be back to original state
    await expect(page.locator("text=2 节点")).toBeVisible()
    await expect(page.locator("text=1 边")).toBeVisible()
  })

  test("连续文本输入合并为单次撤销", async ({ page }) => {
    await expect(page.locator("text=2 节点")).toBeVisible()

    // Expand first node — the title field has default value "市场调研"
    await expandNode(page, 0)
    const titleInput = page.locator('[data-testid="node-card-0"] input[placeholder="节点标题"]')
    await expect(titleInput).toHaveValue("市场调研")

    // Clear the field and blur to end the merge session (creates one undo entry)
    await titleInput.clear()
    await titleInput.blur()
    await page.waitForTimeout(100)

    // Re-focus and type multiple characters — these should be merged into a single undo entry
    await titleInput.click()
    await titleInput.pressSequentially("hello", { delay: 30 })
    await titleInput.blur()
    await page.waitForTimeout(200)

    // Should show the typed value
    await expect(titleInput).toHaveValue("hello")

    // First undo → reverts all typed characters at once (merged entry → cleared state)
    await page.locator('[data-testid="undo-btn"]').click()
    await page.waitForTimeout(200)
    await expect(titleInput).toHaveValue("")

    // Second undo → reverts the clear, back to original
    await page.locator('[data-testid="undo-btn"]').click()
    await page.waitForTimeout(200)
    await expect(titleInput).toHaveValue("市场调研")
  })
})

// ── Phase 6.5: JSON Import/Export & Draft Auto-Save ──────────

const DRAFT_STORAGE_KEY = "boss_graph_template_draft_v1"

const VALID_DRAFT = {
  name: "导入测试模板",
  description: "Playwright 导入测试",
  goal_hint: "验证 JSON 导入功能",
  nodes: [
    { id: "alpha", agent_id: "research", task_type: "research_brief", title: "调研", prompt: "调研市场" },
    { id: "beta", agent_id: "marketing", task_type: "copywriting", title: "营销", prompt: "生成方案" },
  ],
  edges: [{ from_node: "alpha", to_node: "beta", handoff_type: "context" }],
}

const INVALID_DAG_DRAFT = {
  name: "自环模板",
  description: "有自环",
  goal_hint: "",
  nodes: [
    { id: "a", agent_id: "a", task_type: "", title: "A", prompt: "" },
  ],
  edges: [{ from_node: "a", to_node: "a", handoff_type: "context" }],
}

const CYCLE_DRAFT = {
  name: "循环模板",
  description: "有循环",
  goal_hint: "",
  nodes: [
    { id: "x", agent_id: "x", task_type: "", title: "X", prompt: "" },
    { id: "y", agent_id: "y", task_type: "", title: "Y", prompt: "" },
  ],
  edges: [
    { from_node: "x", to_node: "y", handoff_type: "context" },
    { from_node: "y", to_node: "x", handoff_type: "context" },
  ],
}

function jsonUpload(data: unknown, name = "graph-template.json") {
  return {
    name,
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(data, null, 2), "utf-8"),
  }
}

test.describe("Phase 6.5 — JSON 导出", () => {
  test.beforeEach(async ({ page }) => {
    await goToBoss(page)
    await openCreateForm(page)
  })

  test("导出 JSON 按钮可见", async ({ page }) => {
    await expect(page.locator("button", { hasText: "导出 JSON" })).toBeVisible()
  })

  test("导出的 JSON 包含正确字段", async ({ page }) => {
    // Intercept the download event
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.locator("button", { hasText: "导出 JSON" }).click(),
    ])

    const suggestedFilename = download.suggestedFilename()
    expect(suggestedFilename).toMatch(/^graph-template-.*\.json$/)

    const path = await download.path()
    const content = JSON.parse(readFileSync(path, "utf-8"))

    // Should have the GraphTemplateDraft schema
    expect(content).toHaveProperty("name")
    expect(content).toHaveProperty("description")
    expect(content).toHaveProperty("goal_hint")
    expect(content).toHaveProperty("nodes")
    expect(content).toHaveProperty("edges")
    expect(Array.isArray(content.nodes)).toBe(true)
    expect(Array.isArray(content.edges)).toBe(true)
    // Default draft has 2 nodes
    expect(content.nodes.length).toBe(2)
    expect(content.edges.length).toBe(1)
    // Verify node fields
    expect(content.nodes[0]).toHaveProperty("id")
    expect(content.nodes[0]).toHaveProperty("agent_id")
    expect(content.nodes[0]).toHaveProperty("task_type")
    expect(content.nodes[0]).toHaveProperty("title")
    expect(content.nodes[0]).toHaveProperty("prompt")
  })
})

test.describe("Phase 6.5 — JSON 导入", () => {
  test.beforeEach(async ({ page }) => {
    // Clear any saved draft first
    await page.goto("/app?page=boss")
    await page.evaluate((key) => localStorage.removeItem(key), DRAFT_STORAGE_KEY)
    await page.waitForTimeout(500)
  })

  test("有效 JSON 导入成功，进入新建模式", async ({ page }) => {
    await goToBoss(page)
    // Dismiss any restore dialog
    const cancelBtn = page.locator('[data-testid="confirm-dialog-cancel"]')
    if (await cancelBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
      await cancelBtn.click()
      await page.waitForTimeout(300)
    }

    // Trigger import via file input
    const fileInput = page.locator('input[type="file"][accept=".json,application/json"]')
    await fileInput.setInputFiles(jsonUpload(VALID_DRAFT))
    await page.waitForTimeout(500)

    // Should enter create form with imported data
    await expect(page.getByRole("heading", { name: "创建 Graph Template" })).toBeVisible()
    const nameInput = page.locator('input[placeholder="模板名称"]')
    await expect(nameInput).toHaveValue("导入测试模板")

    // DagEditor should show 2 nodes, 1 edge
    await expect(page.locator("text=2 节点")).toBeVisible()
    await expect(page.locator("text=1 边")).toBeVisible()

    // Should be in "create" mode (no "更新模板" button)
    await expect(page.locator("button", { hasText: "保存模板" })).toBeVisible()
    await expect(page.locator("button", { hasText: "更新模板" })).not.toBeVisible()

  })

  test("非合法 JSON 不覆盖草稿，显示错误", async ({ page }) => {
    await goToBoss(page)
    const cancelBtn = page.locator('[data-testid="confirm-dialog-cancel"]')
    if (await cancelBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
      await cancelBtn.click()
      await page.waitForTimeout(300)
    }

    // Open create form first to have a draft
    await openCreateForm(page)
    await fillTemplateName(page, "原始草稿")

    const fileInput = page.locator('input[type="file"][accept=".json,application/json"]')
    await fileInput.setInputFiles({
      name: "invalid.json",
      mimeType: "application/json",
      buffer: Buffer.from("not valid json {{{", "utf-8"),
    })
    await page.waitForTimeout(500)

    // Should show import error
    await expect(page.locator("text=导入失败")).toBeVisible()
    await expect(page.locator("text=JSON 解析失败")).toBeVisible()

    // Original draft should NOT be overwritten
    const nameInput = page.locator('input[placeholder="模板名称"]')
    await expect(nameInput).toHaveValue("原始草稿")

  })

  test("无效 DAG 结构被拦截（自环）", async ({ page }) => {
    await goToBoss(page)
    const cancelBtn = page.locator('[data-testid="confirm-dialog-cancel"]')
    if (await cancelBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
      await cancelBtn.click()
      await page.waitForTimeout(300)
    }

    const fileInput = page.locator('input[type="file"][accept=".json,application/json"]')
    await fileInput.setInputFiles(jsonUpload(INVALID_DAG_DRAFT))
    await page.waitForTimeout(500)

    // Should show import error with self-loop message
    await expect(page.locator("text=导入失败")).toBeVisible()
    await expect(page.locator("text=自环")).toBeVisible()

  })

  test("无效 DAG 结构被拦截（循环）", async ({ page }) => {
    await goToBoss(page)
    const cancelBtn = page.locator('[data-testid="confirm-dialog-cancel"]')
    if (await cancelBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
      await cancelBtn.click()
      await page.waitForTimeout(300)
    }

    const fileInput = page.locator('input[type="file"][accept=".json,application/json"]')
    await fileInput.setInputFiles(jsonUpload(CYCLE_DRAFT))
    await page.waitForTimeout(500)

    await expect(page.locator("text=导入失败")).toBeVisible()
    await expect(page.locator("text=循环")).toBeVisible()

  })

  test("缺少必要字段被拦截", async ({ page }) => {
    await goToBoss(page)
    const cancelBtn = page.locator('[data-testid="confirm-dialog-cancel"]')
    if (await cancelBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
      await cancelBtn.click()
      await page.waitForTimeout(300)
    }

    const fileInput = page.locator('input[type="file"][accept=".json,application/json"]')
    await fileInput.setInputFiles(jsonUpload({ name: "缺字段" }))
    await page.waitForTimeout(500)

    await expect(page.locator("text=导入失败")).toBeVisible()
    await expect(page.locator("text=nodes")).toBeVisible()

  })
})

test.describe("Phase 6.5 — 草稿自动保存与恢复", () => {
  test.beforeEach(async ({ page }) => {
    // Clear any saved draft
    await page.goto("/app?page=boss")
    await page.evaluate((key) => localStorage.removeItem(key), DRAFT_STORAGE_KEY)
    await page.waitForTimeout(500)
  })

  test("编辑草稿后自动保存到 localStorage", async ({ page }) => {
    await goToBoss(page)
    const cancelBtn = page.locator('[data-testid="confirm-dialog-cancel"]')
    if (await cancelBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
      await cancelBtn.click()
      await page.waitForTimeout(300)
    }

    await openCreateForm(page)
    await fillTemplateName(page, "自动保存测试")

    // Wait for debounced save (500ms + buffer)
    await page.waitForTimeout(1200)

    // Check localStorage
    const saved = await page.evaluate((key) => {
      const raw = localStorage.getItem(key)
      return raw ? JSON.parse(raw) : null
    }, DRAFT_STORAGE_KEY)

    expect(saved).not.toBeNull()
    expect(saved.name).toBe("自动保存测试")
    expect(saved.nodes.length).toBe(2) // default draft
  })

  test("刷新页面后提示恢复草稿", async ({ page }) => {
    await goToBoss(page)
    const cancelBtn = page.locator('[data-testid="confirm-dialog-cancel"]')
    if (await cancelBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
      await cancelBtn.click()
      await page.waitForTimeout(300)
    }

    await openCreateForm(page)
    await fillTemplateName(page, "刷新恢复测试")
    await page.waitForTimeout(1200) // wait for save

    // Reload the page
    await page.reload()
    await page.waitForTimeout(1500)

    // Should show restore dialog
    await expect(page.locator('[data-testid="confirm-dialog"]')).toBeVisible({ timeout: 5000 })
    await expect(page.locator("text=发现未保存草稿")).toBeVisible()
    await expect(page.locator("text=刷新恢复测试")).toBeVisible()
  })

  test("恢复草稿后数据正确", async ({ page }) => {
    await goToBoss(page)
    const cancelBtn = page.locator('[data-testid="confirm-dialog-cancel"]')
    if (await cancelBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
      await cancelBtn.click()
      await page.waitForTimeout(300)
    }

    await openCreateForm(page)
    await fillTemplateName(page, "恢复确认测试")
    await page.waitForTimeout(1200)

    await page.reload()
    await page.waitForTimeout(1500)

    // Click restore
    await page.locator('[data-testid="confirm-dialog-confirm"]').click()
    await page.waitForTimeout(500)

    // Form should be open with restored data
    await expect(page.getByRole("heading", { name: "创建 Graph Template" })).toBeVisible()
    const nameInput = page.locator('input[placeholder="模板名称"]')
    await expect(nameInput).toHaveValue("恢复确认测试")
    await expect(page.locator("text=2 节点")).toBeVisible()
  })

  test("放弃草稿后 localStorage 被清理", async ({ page }) => {
    // Set a draft in localStorage directly
    await page.goto("/app?page=boss")
    await page.evaluate(({ key, draft }) => {
      localStorage.setItem(key, JSON.stringify(draft))
    }, { key: DRAFT_STORAGE_KEY, draft: VALID_DRAFT })
    await page.waitForTimeout(300)

    // Reload to trigger restore prompt
    await page.reload()
    await page.waitForTimeout(1500)

    // Should show restore dialog
    await expect(page.locator('[data-testid="confirm-dialog"]')).toBeVisible({ timeout: 5000 })

    // Click discard
    await page.locator('[data-testid="confirm-dialog-cancel"]').click()
    await page.waitForTimeout(500)

    // localStorage should be cleared
    const stored = await page.evaluate((key) => localStorage.getItem(key), DRAFT_STORAGE_KEY)
    expect(stored).toBeNull()
  })

  test("关闭恢复提示不会删除草稿", async ({ page }) => {
    await page.evaluate(({ key, draft }) => {
      localStorage.setItem(key, JSON.stringify(draft))
    }, { key: DRAFT_STORAGE_KEY, draft: VALID_DRAFT })

    await page.reload()
    await expect(page.locator('[data-testid="confirm-dialog"]')).toBeVisible({ timeout: 5000 })
    await page.keyboard.press("Escape")

    await expect(page.locator('[data-testid="confirm-dialog"]')).not.toBeVisible()
    const stored = await page.evaluate((key) => localStorage.getItem(key), DRAFT_STORAGE_KEY)
    expect(stored).not.toBeNull()
  })

  test("损坏草稿会被清理且不会提示恢复", async ({ page }) => {
    await page.evaluate((key) => {
      localStorage.setItem(key, JSON.stringify({
        name: "损坏草稿",
        nodes: [null],
        edges: [],
      }))
    }, DRAFT_STORAGE_KEY)

    await page.reload()
    await page.waitForTimeout(800)

    await expect(page.locator('[data-testid="confirm-dialog"]')).not.toBeVisible()
    const stored = await page.evaluate((key) => localStorage.getItem(key), DRAFT_STORAGE_KEY)
    expect(stored).toBeNull()
  })

  test("保存模板成功后 localStorage 被清理", async ({ page, request }) => {
    await goToBoss(page)
    const cancelBtn = page.locator('[data-testid="confirm-dialog-cancel"]')
    if (await cancelBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
      await cancelBtn.click()
      await page.waitForTimeout(300)
    }

    const templateName = `DraftCleanup ${Date.now()}`
    await openCreateForm(page)
    await fillTemplateName(page, templateName)
    await page.waitForTimeout(1200) // wait for auto-save

    // Verify draft exists in localStorage
    const beforeSave = await page.evaluate((key) => localStorage.getItem(key), DRAFT_STORAGE_KEY)
    expect(beforeSave).not.toBeNull()

    // Save the template
    await page.locator("button", { hasText: "保存模板" }).click()
    await page.waitForTimeout(2000)

    // localStorage should be cleared
    const afterSave = await page.evaluate((key) => localStorage.getItem(key), DRAFT_STORAGE_KEY)
    expect(afterSave).toBeNull()

    // Cleanup: delete the created template
    const listResponse = await request.get("/boss/graph/templates")
    const listBody = await listResponse.json()
    const created = listBody.templates.find((t: { name: string }) => t.name === templateName)
    if (created) {
      await request.delete(`/boss/graph/templates/${created.template_id}`)
    }
  })

  test("取消编辑后 localStorage 被清理", async ({ page }) => {
    await goToBoss(page)
    const cancelBtn = page.locator('[data-testid="confirm-dialog-cancel"]')
    if (await cancelBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
      await cancelBtn.click()
      await page.waitForTimeout(300)
    }

    await openCreateForm(page)
    await fillTemplateName(page, "取消清理测试")
    await page.waitForTimeout(1200)

    // Verify draft saved
    const before = await page.evaluate((key) => localStorage.getItem(key), DRAFT_STORAGE_KEY)
    expect(before).not.toBeNull()

    // Click cancel
    await page.locator("button", { hasText: "取消" }).click()
    await page.waitForTimeout(500)

    // localStorage should be cleared
    const after = await page.evaluate((key) => localStorage.getItem(key), DRAFT_STORAGE_KEY)
    expect(after).toBeNull()
  })
})

test.describe("Phase 6.5 — 导入后 Undo/Redo 正确 reset", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/app?page=boss")
    await page.evaluate((key) => localStorage.removeItem(key), DRAFT_STORAGE_KEY)
    await page.waitForTimeout(500)
  })

  test("导入后撤销回到导入前状态不可用（history reset）", async ({ page }) => {
    await goToBoss(page)
    const cancelBtn = page.locator('[data-testid="confirm-dialog-cancel"]')
    if (await cancelBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
      await cancelBtn.click()
      await page.waitForTimeout(300)
    }

    const fileInput = page.locator('input[type="file"][accept=".json,application/json"]')
    await fileInput.setInputFiles(jsonUpload(VALID_DRAFT))
    await page.waitForTimeout(500)

    // Should show imported data
    await expect(page.locator("text=2 节点")).toBeVisible()

    // Undo button should be disabled (history was reset on import)
    const undoBtn = page.locator('[data-testid="undo-btn"]')
    await expect(undoBtn).toBeDisabled()

  })

  test("恢复草稿后撤销按钮正确 reset", async ({ page }) => {
    // Set a draft directly
    await page.goto("/app?page=boss")
    await page.evaluate(({ key, draft }) => {
      localStorage.setItem(key, JSON.stringify(draft))
    }, { key: DRAFT_STORAGE_KEY, draft: VALID_DRAFT })
    await page.waitForTimeout(300)

    // Reload
    await page.reload()
    await page.waitForTimeout(1500)

    // Restore
    await page.locator('[data-testid="confirm-dialog-confirm"]').click()
    await page.waitForTimeout(500)

    // Undo should be disabled (fresh history)
    const undoBtn = page.locator('[data-testid="undo-btn"]')
    await expect(undoBtn).toBeDisabled()
  })
})

// ── Phase 6.6: Version History & Rollback ─────────────────────────────────

async function updateTemplateFixture(
  request: APIRequestContext,
  templateId: string,
  payload: { name: string; nodes: Array<Record<string, string>>; edges?: Array<Record<string, string>>; description?: string; goal_hint?: string },
) {
  const response = await request.put(`/boss/graph/templates/${templateId}`, { data: payload })
  expect(response.ok()).toBeTruthy()
}

test.describe("Phase 6.6 — Version History & Rollback", () => {
  let createdTemplateId: string | null = null

  test.afterEach(async ({ request }) => {
    await deleteTemplateFixture(request, createdTemplateId)
    createdTemplateId = null
  })

  test("版本按钮可见，点击打开版本历史面板（空状态）", async ({ page, request }) => {
    createdTemplateId = await createTemplateFixture(request, "版本按钮测试")
    await goToBoss(page)

    // 找到模板卡片上的「版本」按钮
    const versionBtn = page.locator("button", { hasText: "版本" }).first()
    await expect(versionBtn).toBeVisible()
    await versionBtn.click()
    await page.waitForTimeout(500)

    // 应显示版本历史面板
    await expect(page.getByRole("heading", { name: "版本历史 / 版本按钮测试" })).toBeVisible()
    // 空状态提示
    await expect(page.locator("text=暂无版本历史")).toBeVisible()
  })

  test("更新模板后版本历史显示一个版本", async ({ page, request }) => {
    createdTemplateId = await createTemplateFixture(request, "V1-版本测试")

    // 通过 API 更新模板（产生版本）
    await updateTemplateFixture(request, createdTemplateId, {
      name: "V2-版本测试",
      nodes: [
        { id: "research", agent_id: "research", title: "调研", prompt: "做调研" },
        { id: "marketing", agent_id: "marketing", title: "营销", prompt: "做营销" },
      ],
    })

    await goToBoss(page)

    // 点击版本按钮
    const versionBtn = page.locator("button", { hasText: "版本" }).first()
    await versionBtn.click()
    await page.waitForTimeout(500)

    // 应显示 1 个版本，名称为 V1
    await expect(page.locator("text=V1-版本测试")).toBeVisible()
    await expect(page.getByText("2 节点", { exact: true }).last()).toBeVisible()
  })

  test("回滚到旧版本", async ({ page, request }) => {
    createdTemplateId = await createTemplateFixture(request, "原始版本")

    // 更新模板
    await updateTemplateFixture(request, createdTemplateId, {
      name: "更新后版本",
      nodes: [
        { id: "research", agent_id: "research", title: "调研", prompt: "做调研" },
        { id: "marketing", agent_id: "marketing", title: "营销", prompt: "做营销" },
      ],
    })

    await goToBoss(page)

    // 点击版本按钮
    const versionBtn = page.locator("button", { hasText: "版本" }).first()
    await versionBtn.click()
    await page.waitForTimeout(500)

    // 点击回滚按钮
    const rollbackBtn = page.locator("button", { hasText: "回滚" }).first()
    await rollbackBtn.click()
    await page.waitForTimeout(300)

    // 确认对话框
    await expect(page.getByRole("heading", { name: "确认回滚", exact: true })).toBeVisible()
    await expect(page.locator("text=当前状态会自动保存为新版本")).toBeVisible()

    // 确认回滚
    await page.locator('[data-testid="confirm-dialog-confirm"]').click()
    await page.waitForTimeout(1000)

    // 模板应恢复为原始版本并进入编辑模式
    await expect(page.getByRole("heading", { name: "编辑 Graph Template" })).toBeVisible()
    await expect(page.locator('input[placeholder="模板名称"]')).toHaveValue("原始版本")
  })

  test("版本详情查看", async ({ page, request }) => {
    createdTemplateId = await createTemplateFixture(request, "详情测试")

    await updateTemplateFixture(request, createdTemplateId, {
      name: "更新后",
      nodes: [
        { id: "research", agent_id: "research", title: "调研", prompt: "做调研" },
        { id: "marketing", agent_id: "marketing", title: "营销", prompt: "做营销" },
      ],
    })

    await goToBoss(page)

    // 打开版本面板
    const versionBtn = page.locator("button", { hasText: "版本" }).first()
    await versionBtn.click()
    await page.waitForTimeout(500)

    // 点击查看按钮
    const viewBtn = page.locator("button", { hasText: "查看" }).first()
    await viewBtn.click()
    await page.waitForTimeout(500)

    // 应显示版本详情 JSON
    await expect(page.locator("text=版本详情")).toBeVisible()
    await expect(page.locator("pre")).toBeVisible()
  })

  test("版本 API 失败时在面板内显示错误", async ({ page, request }) => {
    createdTemplateId = await createTemplateFixture(request, "版本错误测试")
    await page.route("**/boss/graph/templates/*/versions", async (route) => {
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ detail: "模拟版本服务失败" }),
      })
    })
    await goToBoss(page)

    const versionBtn = page.locator("button", { hasText: "版本" }).first()
    await versionBtn.click()

    await expect(page.locator("text=版本操作失败")).toBeVisible()
    await expect(page.locator("text=暂无版本历史")).not.toBeVisible()
  })
})

// ── Phase 6.7: Version Metadata & Compare ────────────────────────────────

test.describe("Phase 6.7 — Version Metadata & Compare", () => {
  let createdTemplateId: string | null = null

  test.afterEach(async ({ request }) => {
    await deleteTemplateFixture(request, createdTemplateId)
    createdTemplateId = null
  })

  test("编辑版本标签和备注", async ({ page, request }) => {
    createdTemplateId = await createTemplateFixture(request, "元数据原始版本")
    await updateTemplateFixture(request, createdTemplateId, {
      name: "元数据当前版本",
      nodes: [
        { id: "research", agent_id: "research", title: "市场调研", prompt: "调研市场" },
        { id: "marketing", agent_id: "marketing", title: "营销方案", prompt: "生成营销方案" },
      ],
      edges: [{ from_node: "research", to_node: "marketing", handoff_type: "context" }],
    })
    await goToBoss(page)

    await page.locator("button", { hasText: "版本" }).first().click()
    await page.locator("button", { hasText: "备注" }).first().click()
    await page.getByTestId("version-label-input").fill("发布前备份")
    await page.getByTestId("version-note-input").fill("确认上线前的稳定版本")
    await page.getByTestId("version-meta-save").click()

    await expect(page.getByText("发布前备份", { exact: true })).toBeVisible()
    await expect(page.getByText("确认上线前的稳定版本", { exact: true })).toBeVisible()
  })

  test("选择两个历史版本并展示差异", async ({ page, request }) => {
    createdTemplateId = await createTemplateFixture(request, "版本一")
    await updateTemplateFixture(request, createdTemplateId, {
      name: "版本二",
      nodes: [
        { id: "research", agent_id: "research", title: "调研二", prompt: "调研市场" },
        { id: "marketing", agent_id: "marketing", title: "营销方案", prompt: "生成营销方案" },
      ],
    })
    await updateTemplateFixture(request, createdTemplateId, {
      name: "版本三",
      nodes: [
        { id: "research", agent_id: "research", title: "调研三", prompt: "调研市场" },
        { id: "marketing", agent_id: "marketing", title: "营销方案", prompt: "生成营销方案" },
      ],
    })
    await goToBoss(page)

    await page.locator("button", { hasText: "版本" }).first().click()
    await page.getByTestId("version-compare-toggle").click()
    const versionChoices = page.locator('[data-testid^="version-compare-ver_"]')
    await expect(versionChoices).toHaveCount(2)
    await versionChoices.nth(0).check()
    await versionChoices.nth(1).check()
    await page.getByTestId("version-compare-run").click()

    const result = page.getByTestId("version-compare-result")
    await expect(result).toBeVisible()
    await expect(result.getByText("基础字段变化", { exact: true })).toBeVisible()
    await expect(result.getByText("节点变化", { exact: true })).toBeVisible()
  })

  test("版本与当前模板相同显示空差异", async ({ page, request }) => {
    createdTemplateId = await createTemplateFixture(request, "完全相同版本")
    await updateTemplateFixture(request, createdTemplateId, {
      name: "完全相同版本",
      description: "Playwright DAG editor fixture",
      goal_hint: "验证 DAG 编辑器",
      nodes: [
        { id: "research", agent_id: "research", title: "市场调研", prompt: "调研市场" },
        { id: "marketing", agent_id: "marketing", title: "营销方案", prompt: "生成营销方案" },
      ],
      edges: [{ from_node: "research", to_node: "marketing", handoff_type: "context" }],
    })
    await goToBoss(page)

    await page.locator("button", { hasText: "版本" }).first().click()
    await page.getByTestId("version-compare-toggle").click()
    await page.locator('[data-testid^="version-compare-ver_"]').first().check()
    await page.getByTestId("version-compare-current").click()
    await page.getByTestId("version-compare-run").click()

    await expect(page.getByTestId("version-compare-result")).toContainText("两个版本完全相同，无差异")
  })

  test("版本对比失败时显示面板错误", async ({ page, request }) => {
    createdTemplateId = await createTemplateFixture(request, "对比错误版本")
    await updateTemplateFixture(request, createdTemplateId, {
      name: "对比错误当前",
      nodes: [
        { id: "research", agent_id: "research", title: "市场调研", prompt: "调研市场" },
        { id: "marketing", agent_id: "marketing", title: "营销方案", prompt: "生成营销方案" },
      ],
    })
    await goToBoss(page)

    await page.locator("button", { hasText: "版本" }).first().click()
    await page.getByTestId("version-compare-toggle").click()
    await page.locator('[data-testid^="version-compare-ver_"]').first().check()
    await page.getByTestId("version-compare-current").click()
    await page.route("**/boss/graph/templates/*/versions/compare?*", async (route) => {
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ detail: "模拟对比服务失败" }),
      })
    })
    await page.getByTestId("version-compare-run").click()

    await expect(page.getByText("版本操作失败", { exact: true })).toBeVisible()
    await expect(page.getByText("关闭提示", { exact: true })).toBeVisible()
  })
})
