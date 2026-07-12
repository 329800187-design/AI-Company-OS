import { test, expect, type APIRequestContext, type Page } from "@playwright/test"
import { existsSync, readFileSync, unlinkSync } from "node:fs"
import { resolve } from "node:path"

// ── Helpers ──────────────────────────────────────────────────────────────────

/** Navigate directly to boss page (skip landing via ?page=boss) */
async function goToBoss(page: Page) {
  await page.goto("/app?page=boss")
  // Wait for Graph Templates panel to be ready — use the DagEditor heading as anchor
  // since it only appears after boss-lite mode renders
  await expect(page.getByText("Graph Templates / 协作图模板")).toBeVisible({ timeout: 15000 })
}

/** Open the create template form */
async function openCreateForm(page: Page) {
  const btn = page.locator("button", { hasText: "创建模板" })
  await expect(btn).toBeVisible({ timeout: 10000 })
  await btn.click()
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

function cleanupAuditArtifact(templateId: string | null) {
  if (!templateId) return
  const auditPath = resolve(process.cwd(), "..", "output", "graph_template_audit", `${templateId}.jsonl`)
  if (existsSync(auditPath)) {
    unlinkSync(auditPath)
  }
}

async function deleteTemplateFixture(
  request: APIRequestContext,
  templateId: string | null,
  options: { keepAudit?: boolean } = {},
) {
  if (!templateId) return
  const response = await request.delete(`/boss/graph/templates/${templateId}`)
  expect(response.ok()).toBeTruthy()
  if (!options.keepAudit) {
    cleanupAuditArtifact(templateId)
  }
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

/** Get the DagEditor container scope (avoids matching template card badges) */
function dagEditor(page: Page) {
  return page.getByRole("heading", { name: "DAG 编辑器", exact: true }).locator("..")
}

function sourceHandle(node: ReturnType<Page["locator"]>) {
  return node.locator(".react-flow__handle.source")
}

function targetHandle(node: ReturnType<Page["locator"]>) {
  return node.locator(".react-flow__handle.target")
}

async function dragHandleTo(
  page: Page,
  source: ReturnType<Page["locator"]>,
  target: ReturnType<Page["locator"]>,
) {
  await source.scrollIntoViewIfNeeded()
  await target.scrollIntoViewIfNeeded()
  const sourceBox = await source.boundingBox()
  const targetBox = await target.boundingBox()

  if (!sourceBox || !targetBox) return

  await page.mouse.move(
    sourceBox.x + sourceBox.width / 2,
    sourceBox.y + sourceBox.height / 2,
  )
  await page.mouse.down()
  await page.mouse.move(
    targetBox.x + targetBox.width / 2,
    targetBox.y + targetBox.height / 2,
    { steps: 10 },
  )
  await page.mouse.up()
  await page.waitForTimeout(300)
}

async function dragNodeBy(
  page: Page,
  node: ReturnType<Page["locator"]>,
  dx: number,
  dy: number,
) {
  await node.scrollIntoViewIfNeeded()
  const box = await node.boundingBox()
  expect(box).not.toBeNull()

  const startX = box!.x + box!.width / 2
  const startY = box!.y + box!.height / 2
  await page.mouse.move(startX, startY)
  await page.mouse.down()
  await page.mouse.move(startX + dx, startY + dy, { steps: 10 })
  await page.mouse.up()
  await page.waitForTimeout(300)
}

async function relativeNodeBox(
  canvas: ReturnType<Page["locator"]>,
  node: ReturnType<Page["locator"]>,
) {
  const canvasBox = await canvas.boundingBox()
  const nodeBox = await node.boundingBox()
  expect(canvasBox).not.toBeNull()
  expect(nodeBox).not.toBeNull()
  return {
    x: nodeBox!.x - canvasBox!.x,
    y: nodeBox!.y - canvasBox!.y,
    width: nodeBox!.width,
    height: nodeBox!.height,
  }
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
    await expect(dagEditor(page).getByText("2 节点", { exact: true })).toBeVisible()
    await expect(dagEditor(page).getByText("1 边", { exact: true })).toBeVisible()
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
    // Wait for templates to load via network
    await expect(page.locator("button", { hasText: "编辑" }).first()).toBeVisible({ timeout: 10000 })

    // Find a template card and click "编辑"
    const editBtn = page.locator("button", { hasText: "编辑" }).first()
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
    await expect(page.locator("button", { hasText: "克隆" }).first()).toBeVisible({ timeout: 10000 })

    const cloneBtn = page.locator("button", { hasText: "克隆" }).first()
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
    await expect(dagEditor(page).getByText("2 节点", { exact: true })).toBeVisible()
    await expect(dagEditor(page).getByText("1 边", { exact: true })).toBeVisible()

    // Click delete → React ConfirmDialog appears
    const nodeSection = page.locator('h5', { hasText: '节点 / Nodes' }).locator('..').locator('[class*="space-y"]').locator('> div').first()
    await nodeSection.locator('button:has(svg)').last().click()
    await page.waitForTimeout(300)

    // Confirm in the React dialog
    await page.locator('[data-testid="confirm-dialog-confirm"]').click()
    await page.waitForTimeout(300)

    // Should now have 1 node and 0 edges (edge referenced "research")
    await expect(dagEditor(page).getByText("1 节点", { exact: true })).toBeVisible()
    await expect(dagEditor(page).getByText("0 边", { exact: true })).toBeVisible()
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
    await expect(dagEditor(page).getByText("2 节点", { exact: true })).toBeVisible()

    await addNode(page)
    await expect(dagEditor(page).getByText("3 节点", { exact: true })).toBeVisible()

    // Click undo button
    await page.locator('[data-testid="undo-btn"]').click()
    await page.waitForTimeout(200)

    await expect(dagEditor(page).getByText("2 节点", { exact: true })).toBeVisible()
  })

  test("重做：添加 → 撤销 → 重做，回到 3 节点", async ({ page }) => {
    await addNode(page)
    await expect(dagEditor(page).getByText("3 节点", { exact: true })).toBeVisible()

    await page.locator('[data-testid="undo-btn"]').click()
    await page.waitForTimeout(200)
    await expect(dagEditor(page).getByText("2 节点", { exact: true })).toBeVisible()

    await page.locator('[data-testid="redo-btn"]').click()
    await page.waitForTimeout(200)
    await expect(dagEditor(page).getByText("3 节点", { exact: true })).toBeVisible()
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
    await expect(dagEditor(page).getByText("2 节点", { exact: true })).toBeVisible()
    await expect(dagEditor(page).getByText("1 边", { exact: true })).toBeVisible()

    // Click delete button → dialog appears
    const nodeSection = page.locator('h5', { hasText: '节点 / Nodes' }).locator('..').locator('[class*="space-y"]').locator('> div').first()
    await nodeSection.locator('button:has(svg)').last().click()
    await page.waitForTimeout(300)

    // Confirm dialog should appear
    await expect(page.locator('[data-testid="confirm-dialog"]')).toBeVisible()

    // Click confirm button
    await page.locator('[data-testid="confirm-dialog-confirm"]').click()
    await page.waitForTimeout(300)

    await expect(dagEditor(page).getByText("1 节点", { exact: true })).toBeVisible()
    await expect(dagEditor(page).getByText("0 边", { exact: true })).toBeVisible()
  })

  test("删除节点 — 取消后数据不变", async ({ page }) => {
    await expect(dagEditor(page).getByText("2 节点", { exact: true })).toBeVisible()
    await expect(dagEditor(page).getByText("1 边", { exact: true })).toBeVisible()

    // Click delete button → dialog appears
    const nodeSection = page.locator('h5', { hasText: '节点 / Nodes' }).locator('..').locator('[class*="space-y"]').locator('> div').first()
    await nodeSection.locator('button:has(svg)').last().click()
    await page.waitForTimeout(300)

    // Click cancel button
    await page.locator('[data-testid="confirm-dialog-cancel"]').click()
    await page.waitForTimeout(300)

    // Data should be unchanged
    await expect(dagEditor(page).getByText("2 节点", { exact: true })).toBeVisible()
    await expect(dagEditor(page).getByText("1 边", { exact: true })).toBeVisible()
  })

  test("删除对话框 — Esc 关闭，数据不变", async ({ page }) => {
    await expect(dagEditor(page).getByText("2 节点", { exact: true })).toBeVisible()

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
    await expect(dagEditor(page).getByText("2 节点", { exact: true })).toBeVisible()
    await expect(dagEditor(page).getByText("1 边", { exact: true })).toBeVisible()
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
    await expect(dagEditor(page).getByText("2 节点", { exact: true })).toBeVisible()
    await expect(dagEditor(page).getByText("1 边", { exact: true })).toBeVisible()

    // Delete first node (confirm dialog)
    const nodeSection = page.locator('h5', { hasText: '节点 / Nodes' }).locator('..').locator('[class*="space-y"]').locator('> div').first()
    await nodeSection.locator('button:has(svg)').last().click()
    await page.waitForTimeout(300)
    await page.locator('[data-testid="confirm-dialog-confirm"]').click()
    await page.waitForTimeout(300)

    // Verify deletion
    await expect(dagEditor(page).getByText("1 节点", { exact: true })).toBeVisible()
    await expect(dagEditor(page).getByText("0 边", { exact: true })).toBeVisible()

    // Undo → restore
    await page.locator('[data-testid="undo-btn"]').click()
    await page.waitForTimeout(300)

    // Should be back to original state
    await expect(dagEditor(page).getByText("2 节点", { exact: true })).toBeVisible()
    await expect(dagEditor(page).getByText("1 边", { exact: true })).toBeVisible()
  })

  test("连续文本输入合并为单次撤销", async ({ page }) => {
    await expect(dagEditor(page).getByText("2 节点", { exact: true })).toBeVisible()

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
    await expect(dagEditor(page).getByText("2 节点", { exact: true })).toBeVisible()
    await expect(dagEditor(page).getByText("1 边", { exact: true })).toBeVisible()

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
    await expect(dagEditor(page).getByText("2 节点", { exact: true })).toBeVisible()
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
      await deleteTemplateFixture(request, created.template_id)
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
    await expect(dagEditor(page).getByText("2 节点", { exact: true })).toBeVisible()

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

// ── Phase 6.8: Audit Log & Pin/Unpin ─────────────────────────────────────

test.describe("Phase 6.8 — 审计日志", () => {
  let createdTemplateId: string | null = null

  test.afterEach(async ({ request }) => {
    await deleteTemplateFixture(request, createdTemplateId)
    createdTemplateId = null
  })

  test("创建模板后审计面板显示 create 事件", async ({ page, request }) => {
    // Create template via API
    createdTemplateId = await createTemplateFixture(request, "审计-create-测试")
    await goToBoss(page)

    // Click the audit button on the template card
    const auditBtn = page.locator('[data-testid="audit-log-btn"]').first()
    await expect(auditBtn).toBeVisible({ timeout: 10000 })
    await auditBtn.click()
    await page.waitForTimeout(500)

    // Audit panel should show a create event
    await expect(page.locator('[data-testid="audit-event-create"]').first()).toBeVisible({ timeout: 5000 })
    await expect(page.locator("text=创建模板").first()).toBeVisible()
  })

  test("克隆模板后审计面板显示 clone 事件", async ({ page, request }) => {
    // Create source template
    const sourceId = await createTemplateFixture(request, "审计-clone-源模板")
    await goToBoss(page)

    // Clone via UI
    await expect(page.locator("button", { hasText: "克隆" }).first()).toBeVisible({ timeout: 10000 })
    await page.locator("button", { hasText: "克隆" }).first().click()
    await page.waitForTimeout(500)

    // Save the clone
    await fillTemplateName(page, "审计-clone-克隆体")
    await page.locator("button", { hasText: "保存模板" }).click()
    await page.waitForTimeout(1500)

    // Find the cloned template and get its ID
    const listResponse = await request.get("/boss/graph/templates")
    const listBody = await listResponse.json()
    const cloned = listBody.templates.find((t: { name: string }) => t.name === "审计-clone-克隆体")
    expect(cloned).toBeTruthy()
    createdTemplateId = cloned.template_id

    // Open audit on the cloned template
    // Navigate to the cloned template's audit via API (UI might have scrolled)
    const auditResponse = await request.get(`/boss/graph/templates/${createdTemplateId}/audit`)
    expect(auditResponse.ok()).toBeTruthy()
    const auditBody = await auditResponse.json()
    const cloneEvents = auditBody.events.filter((e: { event_type: string }) => e.event_type === "clone")
    expect(cloneEvents.length).toBeGreaterThanOrEqual(1)
    expect(cloneEvents[0].details.source_template_id).toBe(sourceId)

    // Cleanup source
    await deleteTemplateFixture(request, sourceId)
  })

  test("审计面板事件筛选功能", async ({ page, request }) => {
    createdTemplateId = await createTemplateFixture(request, "审计-filter-测试")
    // Update to generate another event type
    await updateTemplateFixture(request, createdTemplateId, {
      name: "审计-filter-测试-更新",
      nodes: [
        { id: "research", agent_id: "research", title: "调研", prompt: "做调研" },
        { id: "marketing", agent_id: "marketing", title: "营销", prompt: "做营销" },
      ],
    })
    await goToBoss(page)

    // Open audit panel
    await page.locator('[data-testid="audit-log-btn"]').first().click()
    await page.waitForTimeout(500)

    // Should show both create and update events
    await expect(page.locator('[data-testid="audit-event-create"]').first()).toBeVisible({ timeout: 5000 })
    await expect(page.locator('[data-testid="audit-event-update"]').first()).toBeVisible()

    // Filter to only "update"
    await page.locator('[data-testid="audit-filter"]').selectOption("update")
    await page.waitForTimeout(500)

    // Should only show update events
    await expect(page.locator('[data-testid="audit-event-update"]').first()).toBeVisible()
    await expect(page.locator('[data-testid="audit-event-create"]')).toHaveCount(0)
  })

  test("审计 API 返回 deleted=true（模板删除后）", async ({ request }) => {
    // Create and then delete template
    const templateId = await createTemplateFixture(request, "审计-delete-测试")
    await deleteTemplateFixture(request, templateId, { keepAudit: true })

    // Audit API should still return events with deleted=true
    const auditResponse = await request.get(`/boss/graph/templates/${templateId}/audit`)
    expect(auditResponse.ok()).toBeTruthy()
    const auditBody = await auditResponse.json()
    expect(auditBody.deleted).toBe(true)
    expect(auditBody.events.length).toBeGreaterThanOrEqual(1)
    // Should have create and delete events
    const eventTypes = auditBody.events.map((e: { event_type: string }) => e.event_type)
    expect(eventTypes).toContain("create")
    expect(eventTypes).toContain("delete")
    cleanupAuditArtifact(templateId)
  })
})

test.describe("Phase 6.8 — 版本 Pin/Unpin", () => {
  let createdTemplateId: string | null = null

  test.afterEach(async ({ request }) => {
    await deleteTemplateFixture(request, createdTemplateId)
    createdTemplateId = null
  })

  test("版本固定后显示「固定」徽章，取消后消失", async ({ page, request }) => {
    createdTemplateId = await createTemplateFixture(request, "Pin-测试")

    // Update to create a version
    await updateTemplateFixture(request, createdTemplateId, {
      name: "Pin-测试-V2",
      nodes: [
        { id: "research", agent_id: "research", title: "调研", prompt: "做调研" },
        { id: "marketing", agent_id: "marketing", title: "营销", prompt: "做营销" },
      ],
    })

    await goToBoss(page)

    // Open version panel
    await page.locator("button", { hasText: "版本" }).first().click()
    await page.waitForTimeout(500)

    // Pin the first version
    const pinBtn = page.locator('[data-testid^="version-pin-"]').first()
    await expect(pinBtn).toBeVisible({ timeout: 5000 })
    await pinBtn.click()
    await page.waitForTimeout(500)

    // Should show pinned badge
    const pinnedBadge = page.locator('[data-testid^="version-pinned-"]').first()
    await expect(pinnedBadge).toBeVisible({ timeout: 5000 })
    await expect(pinnedBadge).toContainText("固定")

    // Unpin
    const unpinBtn = page.locator('[data-testid^="version-pin-"]').first()
    await unpinBtn.click()
    await page.waitForTimeout(500)

    // Pinned badge should be gone
    await expect(page.locator('[data-testid^="version-pinned-"]').first()).not.toBeVisible()
  })

  test("Pin 操作生成审计事件", async ({ request }) => {
    createdTemplateId = await createTemplateFixture(request, "Pin-audit-测试")

    // Update to create a version
    await updateTemplateFixture(request, createdTemplateId, {
      name: "Pin-audit-测试-V2",
      nodes: [
        { id: "research", agent_id: "research", title: "调研", prompt: "做调研" },
        { id: "marketing", agent_id: "marketing", title: "营销", prompt: "做营销" },
      ],
    })

    // Get version list
    const versionsResponse = await request.get(`/boss/graph/templates/${createdTemplateId}/versions`)
    const versionsBody = await versionsResponse.json()
    const versionId = versionsBody.versions[0].version_id

    // Pin via API
    const pinResponse = await request.post(`/boss/graph/templates/${createdTemplateId}/versions/${versionId}/pin`)
    expect(pinResponse.ok()).toBeTruthy()

    // Check audit log for pin event
    const auditResponse = await request.get(`/boss/graph/templates/${createdTemplateId}/audit`)
    const auditBody = await auditResponse.json()
    const pinEvents = auditBody.events.filter((e: { event_type: string }) => e.event_type === "pin")
    expect(pinEvents.length).toBeGreaterThanOrEqual(1)
    expect(pinEvents[0].details.version_id).toBe(versionId)
  })
})

// ── Canvas Preview (Step 1) ────────────────────────────────────────────────

test.describe("DAG Canvas 预览", () => {
  let createdTemplateId: string | null = null

  test.afterEach(async ({ request }) => {
    await deleteTemplateFixture(request, createdTemplateId)
    createdTemplateId = null
  })

  test("点击预览图能看到画布", async ({ page, request }) => {
    createdTemplateId = await createTemplateFixture(request, "Canvas-预览测试")

    await goToBoss(page)

    // Click the preview button
    const previewBtn = page.locator('[data-testid="preview-canvas-btn"]').first()
    await expect(previewBtn).toBeVisible()
    await previewBtn.click()
    await page.waitForTimeout(500)

    // The canvas container should appear
    const canvas = page.locator('[data-testid="dag-canvas"]').first()
    await expect(canvas).toBeVisible()

    // React Flow container should be rendered inside
    await expect(canvas.locator(".react-flow")).toBeVisible()
  })

  test("节点数量正确渲染", async ({ page, request }) => {
    createdTemplateId = await createTemplateFixture(request, "Canvas-节点测试")

    await goToBoss(page)

    // Expand preview
    const previewBtn = page.locator('[data-testid="preview-canvas-btn"]').first()
    await previewBtn.click()
    await page.waitForTimeout(500)

    const canvas = page.locator('[data-testid="dag-canvas"]').first()
    await expect(canvas).toBeVisible()

    // Should render 2 nodes (research + marketing from fixture)
    const flowNodes = canvas.locator(".react-flow__node")
    await expect(flowNodes).toHaveCount(2)
  })

  test("空边状态正确显示", async ({ page, request }) => {
    // Create a template with nodes but no edges
    const response = await request.post("/boss/graph/templates", {
      data: {
        name: "Canvas-空边测试",
        description: "无连线模板",
        goal_hint: "测试空边状态",
        nodes: [
          { id: "solo", agent_id: "research", title: "独立节点", prompt: "独立任务" },
        ],
        edges: [],
      },
    })
    expect(response.ok()).toBeTruthy()
    const body = await response.json()
    createdTemplateId = body.template.template_id as string

    await goToBoss(page)

    // Expand preview
    const previewBtn = page.locator('[data-testid="preview-canvas-btn"]').first()
    await previewBtn.click()
    await page.waitForTimeout(500)

    const canvas = page.locator('[data-testid="dag-canvas"]').first()
    await expect(canvas).toBeVisible()

    // "无连线" hint should be visible
    await expect(canvas.getByText("无连线")).toBeVisible()

    // The single node should still render
    const flowNodes = canvas.locator(".react-flow__node")
    await expect(flowNodes).toHaveCount(1)
  })
})

// ── Step 2: Canvas Interaction ────────────────────────────────────────────

test.describe("DAG Canvas 交互", () => {
  let createdTemplateId: string | null = null

  test.afterEach(async ({ request }) => {
    await deleteTemplateFixture(request, createdTemplateId)
    createdTemplateId = null
  })

  test("点击节点显示属性面板", async ({ page, request }) => {
    createdTemplateId = await createTemplateFixture(request, "Canvas-节点点击测试")

    await goToBoss(page)

    // Expand preview
    const previewBtn = page.locator('[data-testid="preview-canvas-btn"]').first()
    await previewBtn.click()
    await page.waitForTimeout(500)

    const canvas = page.locator('[data-testid="dag-canvas"]').first()
    await expect(canvas).toBeVisible()

    // Click the first node
    const firstNode = canvas.locator(".react-flow__node").first()
    await expect(firstNode).toBeVisible()
    await firstNode.click()
    await page.waitForTimeout(300)

    // Detail panel should appear
    const panel = page.locator('[data-testid="dag-detail-panel"]')
    await expect(panel).toBeVisible()

    // Should show node properties
    await expect(panel.getByText("id", { exact: true })).toBeVisible()
    await expect(panel.getByText("agent_id")).toBeVisible()
    await expect(panel.locator('span.font-mono', { hasText: "research" }).first()).toBeVisible()
    await expect(panel.getByText("市场调研")).toBeVisible()

    // Should show edge counts
    await expect(panel.getByText("入边数量")).toBeVisible()
    await expect(panel.getByText("出边数量")).toBeVisible()
  })

  test("点击边显示属性面板", async ({ page, request }) => {
    createdTemplateId = await createTemplateFixture(request, "Canvas-边点击测试")

    await goToBoss(page)

    // Expand preview
    const previewBtn = page.locator('[data-testid="preview-canvas-btn"]').first()
    await previewBtn.click()
    await page.waitForTimeout(500)

    const canvas = page.locator('[data-testid="dag-canvas"]').first()
    await expect(canvas).toBeVisible()

    // Click the edge using its data-testid (set by DagCanvas custom edge)
    // Note: SVG edge paths with zero rendered height are "hidden" per Playwright.
    // Use force:true for SVG path elements — the click still triggers the ReactFlow handler.
    const edge = canvas.locator('[data-testid="edge-research-marketing"]').first()
    await expect(edge).toBeAttached()
    await edge.click({ force: true })
    await page.waitForTimeout(300)

    // Detail panel should appear with edge properties
    const panel = page.locator('[data-testid="dag-detail-panel"]')
    await expect(panel).toBeVisible()

    await expect(panel.getByText("from_node")).toBeVisible()
    await expect(panel.getByText("to_node")).toBeVisible()
    await expect(panel.getByText("handoff_type")).toBeVisible()
    await expect(panel.getByText("context")).toBeVisible()
  })

  test("MiniMap 和 Controls 可见", async ({ page, request }) => {
    createdTemplateId = await createTemplateFixture(request, "Canvas-控件测试")

    await goToBoss(page)

    // Expand preview
    const previewBtn = page.locator('[data-testid="preview-canvas-btn"]').first()
    await previewBtn.click()
    await page.waitForTimeout(500)

    const canvas = page.locator('[data-testid="dag-canvas"]').first()
    await expect(canvas).toBeVisible()

    // MiniMap should exist
    await expect(canvas.locator(".react-flow__minimap")).toBeVisible()

    // Controls should exist
    await expect(canvas.locator(".react-flow__controls")).toBeVisible()
  })
})

// ── Edge Click with Hyphenated Node IDs ─────────────────────────────────────

test.describe("DAG Canvas — 边点击支持含连字符的节点 ID", () => {
  let createdTemplateId: string | null = null

  test.afterEach(async ({ request }) => {
    await deleteTemplateFixture(request, createdTemplateId)
    createdTemplateId = null
  })

  test("点击边显示正确的 from_node 和 to_node（含连字符）", async ({ page, request }) => {
    // Create template with hyphenated node IDs
    const response = await request.post("/boss/graph/templates", {
      data: {
        name: "Canvas-连字符测试",
        description: "验证边点击支持含连字符的节点 ID",
        goal_hint: "测试",
        nodes: [
          { id: "research-agent", agent_id: "research", title: "调研", prompt: "做调研" },
          { id: "marketing-agent", agent_id: "marketing", title: "营销", prompt: "做营销" },
        ],
        edges: [{ from_node: "research-agent", to_node: "marketing-agent", handoff_type: "context" }],
      },
    })
    expect(response.ok()).toBeTruthy()
    const body = await response.json()
    createdTemplateId = body.template.template_id as string

    await goToBoss(page)

    // Expand preview
    const previewBtn = page.locator('[data-testid="preview-canvas-btn"]').first()
    await expect(previewBtn).toBeVisible({ timeout: 10000 })
    await previewBtn.click()
    await page.waitForTimeout(500)

    const canvas = page.locator('[data-testid="dag-canvas"]').first()
    await expect(canvas).toBeVisible()

    // Click the edge using its data-testid
    const edge = canvas.locator('[data-testid="edge-research-agent-marketing-agent"]').first()
    await expect(edge).toBeAttached()
    await edge.click({ force: true })
    await page.waitForTimeout(300)

    // Detail panel should show correct from_node and to_node
    const panel = page.locator('[data-testid="dag-detail-panel"]')
    await expect(panel).toBeVisible()

    await expect(panel.getByText("from_node")).toBeVisible()
    await expect(panel.getByText("to_node")).toBeVisible()
    // Verify the full hyphenated IDs are displayed correctly
    await expect(panel.locator('span.font-mono', { hasText: "research-agent" }).first()).toBeVisible()
    await expect(panel.locator('span.font-mono', { hasText: "marketing-agent" }).first()).toBeVisible()
    await expect(panel.getByText("context")).toBeVisible()
  })
})

// ── Editable Canvas ─────────────────────────────────────────────────────────

test.describe("DAG Canvas 编辑", () => {
  test.beforeEach(async ({ page }) => {
    await goToBoss(page)
    await openCreateForm(page)
  })

  test("点击节点可编辑属性并同步到画布", async ({ page }) => {
    // The editable canvas should be visible in the create form
    const canvas = page.locator('[data-testid="dag-canvas"]').first()
    await expect(canvas).toBeVisible({ timeout: 5000 })

    // Click the first node
    const firstNode = canvas.locator(".react-flow__node").first()
    await expect(firstNode).toBeVisible()
    await firstNode.click()
    await page.waitForTimeout(300)

    // Detail panel should appear with editable fields
    const panel = page.locator('[data-testid="dag-detail-panel"]')
    await expect(panel).toBeVisible()

    // The title field should be editable (contains "市场调研" from default draft)
    const titleInput = panel.locator('[data-testid="canvas-edit-title"]')
    await expect(titleInput).toBeVisible()
    await expect(titleInput).toHaveValue("市场调研")

    // Edit the title
    await titleInput.clear()
    await titleInput.fill("新标题")
    await titleInput.blur()
    await page.waitForTimeout(300)

    // The node label in the canvas should update
    await expect(canvas.locator(".react-flow__node").first().locator("text=新标题")).toBeVisible()
  })

  test("点击边可编辑 handoff_type", async ({ page }) => {
    const canvas = page.locator('[data-testid="dag-canvas"]').first()
    await expect(canvas).toBeVisible({ timeout: 5000 })

    // Click the edge
    const edge = canvas.locator('[data-testid="edge-research-marketing"]').first()
    await expect(edge).toBeAttached()
    await edge.click({ force: true })
    await page.waitForTimeout(300)

    const panel = page.locator('[data-testid="dag-detail-panel"]')
    await expect(panel).toBeVisible()

    // The handoff_type field should be editable
    const handoffInput = panel.locator('[data-testid="canvas-edit-handoff_type"]')
    await expect(handoffInput).toBeVisible()
    await expect(handoffInput).toHaveValue("context")

    // Edit handoff_type
    await handoffInput.clear()
    await handoffInput.fill("data_only")
    await handoffInput.blur()
    await page.waitForTimeout(300)

    // Close and re-click the edge to verify the change persisted
    await canvas.locator(".react-flow").click({ position: { x: 10, y: 10 } })
    await page.waitForTimeout(200)

    await edge.click({ force: true })
    await page.waitForTimeout(300)

    await expect(panel.locator('[data-testid="canvas-edit-handoff_type"]')).toHaveValue("data_only")
  })

  test("删除节点自动清理关联边", async ({ page }) => {
    // Default draft: 2 nodes, 1 edge
    await expect(dagEditor(page).getByText("2 节点", { exact: true })).toBeVisible()
    await expect(dagEditor(page).getByText("1 边", { exact: true })).toBeVisible()

    const canvas = page.locator('[data-testid="dag-canvas"]').first()
    await expect(canvas).toBeVisible({ timeout: 5000 })

    // Click the first node
    const firstNode = canvas.locator(".react-flow__node").first()
    await firstNode.click()
    await page.waitForTimeout(300)

    const panel = page.locator('[data-testid="dag-detail-panel"]')
    await expect(panel).toBeVisible()

    // Click delete button
    await panel.locator('[data-testid="canvas-delete-node-btn"]').click()
    await page.waitForTimeout(200)

    // Confirm deletion
    await panel.locator('[data-testid="canvas-confirm-delete-node"]').click()
    await page.waitForTimeout(300)

    // DagEditor badge should show 1 node, 0 edges
    await expect(dagEditor(page).getByText("1 节点", { exact: true })).toBeVisible()
    await expect(dagEditor(page).getByText("0 边", { exact: true })).toBeVisible()

    // Canvas should render 1 node
    const flowNodes = canvas.locator(".react-flow__node")
    await expect(flowNodes).toHaveCount(1)
  })

  test("删除边", async ({ page }) => {
    // Default draft: 2 nodes, 1 edge
    await expect(dagEditor(page).getByText("2 节点", { exact: true })).toBeVisible()
    await expect(dagEditor(page).getByText("1 边", { exact: true })).toBeVisible()

    const canvas = page.locator('[data-testid="dag-canvas"]').first()
    await expect(canvas).toBeVisible({ timeout: 5000 })

    // Click the edge
    const edge = canvas.locator('[data-testid="edge-research-marketing"]').first()
    await expect(edge).toBeAttached()
    await edge.click({ force: true })
    await page.waitForTimeout(300)

    const panel = page.locator('[data-testid="dag-detail-panel"]')
    await expect(panel).toBeVisible()

    // Click delete edge button
    await panel.locator('[data-testid="canvas-delete-edge-btn"]').click()
    await page.waitForTimeout(300)

    // DagEditor badge should show 2 nodes, 0 edges
    await expect(dagEditor(page).getByText("2 节点", { exact: true })).toBeVisible()
    await expect(dagEditor(page).getByText("0 边", { exact: true })).toBeVisible()
  })
})

// ── agent_id 编辑 ──────────────────────────────────────────────────────────

test.describe("DAG Canvas 编辑 — agent_id 可编辑", () => {
  test.beforeEach(async ({ page }) => {
    await goToBoss(page)
    await openCreateForm(page)
  })

  test("编辑 agent_id 并同步到画布", async ({ page }) => {
    const canvas = page.locator('[data-testid="dag-canvas"]').first()
    await expect(canvas).toBeVisible({ timeout: 5000 })

    // Click first node (research)
    const firstNode = canvas.locator(".react-flow__node").first()
    await firstNode.click()
    await page.waitForTimeout(300)

    const panel = page.locator('[data-testid="dag-detail-panel"]')
    await expect(panel).toBeVisible()

    // agent_id should be editable and show "research"
    const agentInput = panel.locator('[data-testid="canvas-edit-agent_id"]')
    await expect(agentInput).toBeVisible()
    await expect(agentInput).toHaveValue("research")

    // Edit agent_id
    await agentInput.clear()
    await agentInput.fill("research-v2")
    await agentInput.blur()
    await page.waitForTimeout(300)

    // The node sublabel in the canvas should update to show the new agent_id
    await expect(canvas.locator(".react-flow__node").first().locator("text=research-v2")).toBeVisible()
  })
})

// ── identityKey 同标题切换 ─────────────────────────────────────────────────

test.describe("DAG Canvas 编辑 — 相同标题节点切换", () => {
  test("两个节点 title 相同，编辑后切换，输入框正确重置", async ({ page }) => {
    // Clear any saved draft first
    await page.goto("/app?page=boss")
    await page.evaluate((key) => localStorage.removeItem(key), DRAFT_STORAGE_KEY)
    await page.waitForTimeout(500)

    await goToBoss(page)
    const cancelBtn = page.locator('[data-testid="confirm-dialog-cancel"]')
    if (await cancelBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
      await cancelBtn.click()
      await page.waitForTimeout(300)
    }

    // Import a draft with two nodes that have the same title
    const sameTitleDraft = {
      name: "同标题测试",
      description: "两个节点 title 相同",
      goal_hint: "测试",
      nodes: [
        { id: "node-a", agent_id: "research", task_type: "", title: "相同标题", prompt: "A 的 prompt" },
        { id: "node-b", agent_id: "marketing", task_type: "", title: "相同标题", prompt: "B 的 prompt" },
      ],
      edges: [{ from_node: "node-a", to_node: "node-b", handoff_type: "context" }],
    }
    const fileInput = page.locator('input[type="file"][accept=".json,application/json"]')
    await fileInput.setInputFiles(jsonUpload(sameTitleDraft))
    await page.waitForTimeout(500)

    // The editable canvas should be visible in the create form
    const canvas = page.locator('[data-testid="dag-canvas"]').first()
    await expect(canvas).toBeVisible({ timeout: 5000 })

    // Click first node (node-a)
    const nodes = canvas.locator(".react-flow__node")
    await nodes.first().click()
    await page.waitForTimeout(300)

    const panel = page.locator('[data-testid="dag-detail-panel"]')
    await expect(panel).toBeVisible()

    // Edit title of first node
    const titleInput = panel.locator('[data-testid="canvas-edit-title"]')
    await expect(titleInput).toHaveValue("相同标题")
    await titleInput.clear()
    await titleInput.fill("A 的新标题")
    await titleInput.blur()
    await page.waitForTimeout(300)

    // Verify edit applied
    await expect(titleInput).toHaveValue("A 的新标题")

    // Click pane to deselect
    await canvas.locator(".react-flow").click({ position: { x: 10, y: 10 } })
    await page.waitForTimeout(200)

    // Click second node (node-b) — also has title "相同标题"
    await nodes.nth(1).click()
    await page.waitForTimeout(300)

    // The title input should show "相同标题" (node-b's value), NOT "A 的新标题"
    const titleInput2 = panel.locator('[data-testid="canvas-edit-title"]')
    await expect(titleInput2).toHaveValue("相同标题")
  })
})

// ── Delete/Backspace 快捷键 ───────────────────────────────────────────────

test.describe("DAG Canvas 编辑 — 键盘快捷键", () => {
  test.beforeEach(async ({ page }) => {
    await goToBoss(page)
    await openCreateForm(page)
  })

  test("选中节点后按 Delete 删除节点及关联边", async ({ page }) => {
    await expect(dagEditor(page).getByText("2 节点", { exact: true })).toBeVisible()
    await expect(dagEditor(page).getByText("1 边", { exact: true })).toBeVisible()

    const canvas = page.locator('[data-testid="dag-canvas"]').first()
    await expect(canvas).toBeVisible({ timeout: 5000 })

    // Click first node to select it
    const firstNode = canvas.locator(".react-flow__node").first()
    await firstNode.click()
    await page.waitForTimeout(300)

    // Panel should be visible (confirms selection)
    const panel = page.locator('[data-testid="dag-detail-panel"]')
    await expect(panel).toBeVisible()

    // Press Delete key
    await page.keyboard.press("Delete")
    await page.waitForTimeout(300)

    // Node and edge should be removed
    await expect(dagEditor(page).getByText("1 节点", { exact: true })).toBeVisible()
    await expect(dagEditor(page).getByText("0 边", { exact: true })).toBeVisible()

    // Canvas should render 1 node
    const flowNodes = canvas.locator(".react-flow__node")
    await expect(flowNodes).toHaveCount(1)
  })

  test("输入框聚焦时按 Backspace 不触发删除", async ({ page }) => {
    const canvas = page.locator('[data-testid="dag-canvas"]').first()
    await expect(canvas).toBeVisible({ timeout: 5000 })

    // Click first node to select it
    const firstNode = canvas.locator(".react-flow__node").first()
    await firstNode.click()
    await page.waitForTimeout(300)

    const panel = page.locator('[data-testid="dag-detail-panel"]')
    await expect(panel).toBeVisible()

    // Focus the title input inside the detail panel
    const titleInput = panel.locator('[data-testid="canvas-edit-title"]')
    await titleInput.click()
    await page.waitForTimeout(100)

    // Press Backspace while input is focused — should NOT delete the node
    await page.keyboard.press("Backspace")
    await page.waitForTimeout(200)

    // Both nodes should still exist
    await expect(dagEditor(page).getByText("2 节点", { exact: true })).toBeVisible()
    await expect(dagEditor(page).getByText("1 边", { exact: true })).toBeVisible()

    // Canvas should still render 2 nodes
    const flowNodes = canvas.locator(".react-flow__node")
    await expect(flowNodes).toHaveCount(2)
  })
})

// ── Canvas undo/redo integration ─────────────────────────────────────────

test.describe("DAG Canvas — undo/redo integration", () => {
  test.beforeEach(async ({ page }) => {
    await goToBoss(page)
    await openCreateForm(page)
    // Wait for DagEditor and canvas to be ready
    await expect(dagEditor(page).getByText("2 节点", { exact: true })).toBeVisible()
    const canvas = page.locator('[data-testid="dag-canvas"]').first()
    await expect(canvas).toBeVisible({ timeout: 5000 })
  })

  test("Canvas 编辑节点 title 后点击撤销按钮，Canvas 节点标题回退", async ({ page }) => {
    const canvas = page.locator('[data-testid="dag-canvas"]').first()

    // Click first node in canvas to open detail panel
    const firstNode = canvas.locator(".react-flow__node").first()
    await firstNode.click()
    await page.waitForTimeout(300)

    const panel = page.locator('[data-testid="dag-detail-panel"]')
    await expect(panel).toBeVisible()

    // Edit the title field
    const titleInput = panel.locator('[data-testid="canvas-edit-title"]')
    await titleInput.clear()
    await titleInput.fill("新标题ABC")
    await titleInput.blur()
    await page.waitForTimeout(300)

    // Verify canvas node label updated
    await expect(canvas.locator(".react-flow__node").getByText("新标题ABC")).toBeVisible()

    // Click DagEditor's undo button
    const undoBtn = page.locator('[data-testid="undo-btn"]')
    await undoBtn.click()
    await page.waitForTimeout(300)

    // Canvas title should revert
    await expect(canvas.locator(".react-flow__node").getByText("新标题ABC")).not.toBeVisible()
  })

  test("Canvas 删除节点后撤销，节点和关联边恢复", async ({ page }) => {
    const canvas = page.locator('[data-testid="dag-canvas"]').first()

    // Verify initial state: 2 nodes, 1 edge
    await expect(dagEditor(page).getByText("2 节点", { exact: true })).toBeVisible()
    await expect(dagEditor(page).getByText("1 边", { exact: true })).toBeVisible()

    // Click first node to select it
    const firstNode = canvas.locator(".react-flow__node").first()
    await firstNode.click()
    await page.waitForTimeout(300)

    const panel = page.locator('[data-testid="dag-detail-panel"]')
    await expect(panel).toBeVisible()

    // Delete the node via canvas delete button
    const deleteBtn = panel.locator('[data-testid="canvas-delete-node-btn"]')
    await deleteBtn.click()
    await page.waitForTimeout(200)

    // Confirm deletion
    const confirmBtn = panel.locator('[data-testid="canvas-confirm-delete-node"]')
    await confirmBtn.click()
    await page.waitForTimeout(300)

    // Verify node was deleted: 1 node, 0 edges
    await expect(dagEditor(page).getByText("1 节点", { exact: true })).toBeVisible()
    await expect(dagEditor(page).getByText("0 边", { exact: true })).toBeVisible()

    // Click undo
    const undoBtn = page.locator('[data-testid="undo-btn"]')
    await undoBtn.click()
    await page.waitForTimeout(300)

    // Verify node and edge restored: 2 nodes, 1 edge
    await expect(dagEditor(page).getByText("2 节点", { exact: true })).toBeVisible()
    await expect(dagEditor(page).getByText("1 边", { exact: true })).toBeVisible()
    const flowNodes = canvas.locator(".react-flow__node")
    await expect(flowNodes).toHaveCount(2)
  })

  test("撤销后再重做，删除状态恢复", async ({ page }) => {
    const canvas = page.locator('[data-testid="dag-canvas"]').first()

    // Click first node to select it
    const firstNode = canvas.locator(".react-flow__node").first()
    await firstNode.click()
    await page.waitForTimeout(300)

    const panel = page.locator('[data-testid="dag-detail-panel"]')
    await expect(panel).toBeVisible()

    // Delete the node
    const deleteBtn = panel.locator('[data-testid="canvas-delete-node-btn"]')
    await deleteBtn.click()
    await page.waitForTimeout(200)
    const confirmBtn = panel.locator('[data-testid="canvas-confirm-delete-node"]')
    await confirmBtn.click()
    await page.waitForTimeout(300)

    // Verify deleted
    await expect(dagEditor(page).getByText("1 节点", { exact: true })).toBeVisible()

    // Undo
    const undoBtn = page.locator('[data-testid="undo-btn"]')
    await undoBtn.click()
    await page.waitForTimeout(300)
    await expect(dagEditor(page).getByText("2 节点", { exact: true })).toBeVisible()

    // Redo
    const redoBtn = page.locator('[data-testid="redo-btn"]')
    await redoBtn.click()
    await page.waitForTimeout(300)

    // Delete state should be restored
    await expect(dagEditor(page).getByText("1 节点", { exact: true })).toBeVisible()
    await expect(dagEditor(page).getByText("0 边", { exact: true })).toBeVisible()
    const flowNodes = canvas.locator(".react-flow__node")
    await expect(flowNodes).toHaveCount(1)
  })

  test("boss 页面不出现两个可编辑 Canvas", async ({ page }) => {
    // Only one canvas should exist inside DagEditor (the editable one)
    // The readonly canvases in template cards are separate
    const canvases = page.locator('[data-testid="dag-canvas"]')
    // There should be exactly 1 editable canvas (inside DagEditor)
    // Template preview canvases only appear when expanded, which doesn't happen on form open
    const count = await canvases.count()
    expect(count).toBe(1)
  })
})

// ── Canvas 图形编辑（拖拽连线 + 添加节点）────────────────────────────────

test.describe("DAG Canvas 图形编辑", () => {
  test.beforeEach(async ({ page }) => {
    await goToBoss(page)
    await openCreateForm(page)
    await expect(dagEditor(page).getByText("2 节点", { exact: true })).toBeVisible()
  })

  test("Canvas 添加节点后，DagEditor badge 从 2 节点变 3 节点", async ({ page }) => {
    const canvas = page.locator('[data-testid="dag-canvas"]').first()
    await expect(canvas).toBeVisible({ timeout: 5000 })

    // Click the "添加节点" button inside the canvas
    const addBtn = canvas.locator('[data-testid="canvas-add-node-btn"]')
    await expect(addBtn).toBeVisible()
    await addBtn.click()
    await page.waitForTimeout(300)

    // DagEditor badge should update to 3 nodes
    await expect(dagEditor(page).getByText("3 节点", { exact: true })).toBeVisible()

    // Canvas should render 3 nodes
    const flowNodes = canvas.locator(".react-flow__node")
    await expect(flowNodes).toHaveCount(3)
  })

  test("Canvas 拖拽连线创建边，边数 +1", async ({ page }) => {
    // First add a new node via canvas button
    const canvas = page.locator('[data-testid="dag-canvas"]').first()
    await expect(canvas).toBeVisible({ timeout: 5000 })

    const addBtn = canvas.locator('[data-testid="canvas-add-node-btn"]')
    await addBtn.click()
    await page.waitForTimeout(300)

    // Should now have 3 nodes, 1 edge (original research -> marketing)
    await expect(dagEditor(page).getByText("3 节点", { exact: true })).toBeVisible()
    await expect(dagEditor(page).getByText("1 边", { exact: true })).toBeVisible()

    // Drag from research's source handle to the new node's target handle
    // React Flow handles are rendered as small circles on node edges
    const nodes = canvas.locator(".react-flow__node")
    const sourceNode = nodes.nth(0) // research
    const targetNode = nodes.nth(2) // new node (node_2)

    // Get the source handle (right side of research node) and target handle (left side of new node)
    const source = sourceHandle(sourceNode)
    const target = targetHandle(targetNode)

    await dragHandleTo(page, source, target)

    // Edge count should increase to 2
    await expect(dagEditor(page).getByText("2 边", { exact: true }).first()).toBeVisible()
  })

  test("自环拖拽不新增边", async ({ page }) => {
    const canvas = page.locator('[data-testid="dag-canvas"]').first()
    await expect(canvas).toBeVisible({ timeout: 5000 })

    // Initial: 2 nodes, 1 edge
    await expect(dagEditor(page).getByText("1 边", { exact: true })).toBeVisible()

    // Try to drag from research's source handle to research's target handle (self-loop)
    const firstNode = canvas.locator(".react-flow__node").first()
    const source = sourceHandle(firstNode)
    const target = targetHandle(firstNode)

    await dragHandleTo(page, source, target)

    // Edge count should stay at 1
    await expect(dagEditor(page).getByText("1 边", { exact: true })).toBeVisible()

    // Error toast should appear
    await expect(canvas.locator('[data-testid="canvas-connection-error"]')).toBeVisible()
  })

  test("重复边拖拽不新增边", async ({ page }) => {
    const canvas = page.locator('[data-testid="dag-canvas"]').first()
    await expect(canvas).toBeVisible({ timeout: 5000 })

    // Initial: 2 nodes, 1 edge (research -> marketing)
    await expect(dagEditor(page).getByText("1 边", { exact: true })).toBeVisible()

    // Try to drag from research to marketing again (duplicate edge)
    const sourceNode = canvas.locator(".react-flow__node").nth(0) // research
    const targetNode = canvas.locator(".react-flow__node").nth(1) // marketing

    const source = sourceHandle(sourceNode)
    const target = targetHandle(targetNode)

    await dragHandleTo(page, source, target)

    // Edge count should stay at 1
    await expect(dagEditor(page).getByText("1 边", { exact: true })).toBeVisible()

    // Error toast should appear
    await expect(canvas.locator('[data-testid="canvas-connection-error"]')).toBeVisible()
  })

  test("会造成 cycle 的边拖拽不新增边", async ({ page }) => {
    const canvas = page.locator('[data-testid="dag-canvas"]').first()
    await expect(canvas).toBeVisible({ timeout: 5000 })

    // Initial: 2 nodes, 1 edge (research -> marketing)
    await expect(dagEditor(page).getByText("1 边", { exact: true })).toBeVisible()

    // Try to drag from marketing to research (would create cycle)
    const sourceNode = canvas.locator(".react-flow__node").nth(1) // marketing
    const targetNode = canvas.locator(".react-flow__node").nth(0) // research

    const source = sourceHandle(sourceNode)
    const target = targetHandle(targetNode)

    await dragHandleTo(page, source, target)

    // Edge count should stay at 1
    await expect(dagEditor(page).getByText("1 边", { exact: true })).toBeVisible()

    // Error toast should appear
    await expect(canvas.locator('[data-testid="canvas-connection-error"]')).toBeVisible()
  })

  test("Canvas 新增节点后撤销/重做正常", async ({ page }) => {
    const canvas = page.locator('[data-testid="dag-canvas"]').first()
    await expect(canvas).toBeVisible({ timeout: 5000 })

    // Add node via canvas button
    const addBtn = canvas.locator('[data-testid="canvas-add-node-btn"]')
    await addBtn.click()
    await page.waitForTimeout(300)

    await expect(dagEditor(page).getByText("3 节点", { exact: true })).toBeVisible()

    // Undo
    await page.locator('[data-testid="undo-btn"]').click()
    await page.waitForTimeout(300)
    await expect(dagEditor(page).getByText("2 节点", { exact: true })).toBeVisible()

    // Redo
    await page.locator('[data-testid="redo-btn"]').click()
    await page.waitForTimeout(300)
    await expect(dagEditor(page).getByText("3 节点", { exact: true })).toBeVisible()
  })

  test("Canvas 新增边后撤销/重做正常", async ({ page }) => {
    const canvas = page.locator('[data-testid="dag-canvas"]').first()
    await expect(canvas).toBeVisible({ timeout: 5000 })

    // Add a new node first (so we have a valid non-duplicate target)
    const addBtn = canvas.locator('[data-testid="canvas-add-node-btn"]')
    await addBtn.click()
    await page.waitForTimeout(300)
    await expect(dagEditor(page).getByText("3 节点", { exact: true })).toBeVisible()
    await expect(dagEditor(page).getByText("1 边", { exact: true })).toBeVisible()

    // Drag from research's source to the new node's target
    const nodes = canvas.locator(".react-flow__node")
    const sourceNode = nodes.nth(0) // research
    const targetNode = nodes.nth(2) // new node

    const source = sourceHandle(sourceNode)
    const target = targetHandle(targetNode)

    await dragHandleTo(page, source, target)

    await expect(dagEditor(page).getByText("2 边", { exact: true }).first()).toBeVisible()

    // Undo — edge should be removed
    await page.locator('[data-testid="undo-btn"]').click()
    await page.waitForTimeout(300)
    await expect(dagEditor(page).getByText("1 边", { exact: true })).toBeVisible()

    // Redo — edge should come back
    await page.locator('[data-testid="redo-btn"]').click()
    await page.waitForTimeout(300)
    await expect(dagEditor(page).getByText("2 边", { exact: true }).first()).toBeVisible()
  })
})

// ── Canvas 只读预览不可编辑 ──────────────────────────────────────────────

test.describe("DAG Canvas 只读预览", () => {
  let createdTemplateId: string | null = null

  test.afterEach(async ({ request }) => {
    await deleteTemplateFixture(request, createdTemplateId)
    createdTemplateId = null
  })

  test("只读预览里没有「添加节点」按钮", async ({ page, request }) => {
    createdTemplateId = await createTemplateFixture(request, "Canvas-只读测试")

    await goToBoss(page)

    // Expand the readonly canvas preview
    const previewBtn = page.locator('[data-testid="preview-canvas-btn"]').first()
    await expect(previewBtn).toBeVisible({ timeout: 10000 })
    await previewBtn.click()
    await page.waitForTimeout(500)

    const canvas = page.locator('[data-testid="dag-canvas"]').first()
    await expect(canvas).toBeVisible()

    // "添加节点" button should NOT exist inside the readonly canvas
    const addBtn = canvas.locator('[data-testid="canvas-add-node-btn"]')
    await expect(addBtn).not.toBeVisible()
  })

  test("只读预览里节点不可连线", async ({ page, request }) => {
    createdTemplateId = await createTemplateFixture(request, "Canvas-只读连线测试")

    await goToBoss(page)

    // Expand the readonly canvas preview
    const previewBtn = page.locator('[data-testid="preview-canvas-btn"]').first()
    await expect(previewBtn).toBeVisible({ timeout: 10000 })
    await previewBtn.click()
    await page.waitForTimeout(500)

    const canvas = page.locator('[data-testid="dag-canvas"]').first()
    await expect(canvas).toBeVisible()

    // Handles should be hidden (not interactable)
    // The react-flow__handle elements should have visibility:hidden
    const handles = canvas.locator(".react-flow__handle")
    const count = await handles.count()
    for (let i = 0; i < count; i++) {
      const style = await handles.nth(i).getAttribute("style")
      expect(style).toContain("visibility: hidden")
    }
  })
})

// ── Canvas 节点拖拽 ──────────────────────────────────────────────────────

test.describe("DAG Canvas 节点拖拽", () => {
  test.beforeEach(async ({ page }) => {
    await goToBoss(page)
    await openCreateForm(page)
    await expect(dagEditor(page).getByText("2 节点", { exact: true })).toBeVisible()
  })

  test("editable Canvas 拖拽节点后位置改变", async ({ page }) => {
    const canvas = page.locator('[data-testid="dag-canvas"]').first()
    await expect(canvas).toBeVisible({ timeout: 5000 })

    const firstNode = canvas.locator(".react-flow__node").first()
    const boxBefore = await firstNode.boundingBox()
    expect(boxBefore).not.toBeNull()

    // Drag node 150px right, 50px down
    await dragNodeBy(page, firstNode, 150, 50)

    const boxAfter = await firstNode.boundingBox()
    expect(boxAfter).not.toBeNull()

    // Position should have changed significantly (allow some tolerance for layout shifts)
    const moved = Math.abs(boxAfter!.x - boxBefore!.x) > 20 || Math.abs(boxAfter!.y - boxBefore!.y) > 20
    expect(moved).toBe(true)
  })

  test("自动布局后节点回到 dagre 布局位置", async ({ page }) => {
    const canvas = page.locator('[data-testid="dag-canvas"]').first()
    await expect(canvas).toBeVisible({ timeout: 5000 })

    const firstNode = canvas.locator(".react-flow__node").first()
    const boxBefore = await firstNode.boundingBox()
    expect(boxBefore).not.toBeNull()
    const relBefore = await relativeNodeBox(canvas, firstNode)

    // Drag node to a new position
    await dragNodeBy(page, firstNode, 200, 80)

    // Verify it moved
    const boxDragged = await firstNode.boundingBox()
    expect(boxDragged).not.toBeNull()
    expect(Math.abs(boxDragged!.x - boxBefore!.x) > 20 || Math.abs(boxDragged!.y - boxBefore!.y) > 20).toBe(true)

    // Click auto-layout button
    const autoLayoutBtn = canvas.locator('[data-testid="canvas-auto-layout-btn"]')
    await expect(autoLayoutBtn).toBeVisible()
    await autoLayoutBtn.click()
    await page.waitForTimeout(500)

    // After auto-layout, the node should be back near its original dagre position
    // (within tolerance since fitView may shift things slightly)
    const boxAfterLayout = await firstNode.boundingBox()
    expect(boxAfterLayout).not.toBeNull()
    const relAfterLayout = await relativeNodeBox(canvas, firstNode)
    expect(Math.abs(relAfterLayout.x - relBefore.x)).toBeLessThan(30)
    expect(Math.abs(relAfterLayout.y - relBefore.y)).toBeLessThan(30)
  })

  test("拖拽节点后 DagEditor 节点/边 badge 不变", async ({ page }) => {
    const canvas = page.locator('[data-testid="dag-canvas"]').first()
    await expect(canvas).toBeVisible({ timeout: 5000 })

    // Verify initial badges
    await expect(dagEditor(page).getByText("2 节点", { exact: true })).toBeVisible()
    await expect(dagEditor(page).getByText("1 边", { exact: true })).toBeVisible()

    // Drag a node
    const firstNode = canvas.locator(".react-flow__node").first()
    const box = await firstNode.boundingBox()
    expect(box).not.toBeNull()
    await dragNodeBy(page, firstNode, 100, 50)

    // Badges should be unchanged
    await expect(dagEditor(page).getByText("2 节点", { exact: true })).toBeVisible()
    await expect(dagEditor(page).getByText("1 边", { exact: true })).toBeVisible()
  })

  test("拖拽节点后撤销按钮状态不变化（不产生历史）", async ({ page }) => {
    const canvas = page.locator('[data-testid="dag-canvas"]').first()
    await expect(canvas).toBeVisible({ timeout: 5000 })

    // Undo button should be disabled initially (no edits yet)
    const undoBtn = page.locator('[data-testid="undo-btn"]')
    await expect(undoBtn).toBeDisabled()

    // Drag a node
    const firstNode = canvas.locator(".react-flow__node").first()
    const box = await firstNode.boundingBox()
    expect(box).not.toBeNull()
    await dragNodeBy(page, firstNode, 100, 50)

    // Undo button should still be disabled — drag didn't create history
    await expect(undoBtn).toBeDisabled()
  })

  test("只读预览节点不可拖拽", async ({ page, request }) => {
    // Create a fixture for readonly preview
    const templateId = await createTemplateFixture(request, "Canvas-只读拖拽测试")

    await goToBoss(page)

    // Expand the readonly canvas preview
    const previewBtn = page.locator('[data-testid="preview-canvas-btn"]').first()
    await expect(previewBtn).toBeVisible({ timeout: 10000 })
    await previewBtn.click()
    await page.waitForTimeout(500)

    const readonlyCanvas = page.locator('[data-testid="dag-canvas"]').first()
    await expect(readonlyCanvas).toBeVisible()

    // First node should NOT be draggable
    const firstNode = readonlyCanvas.locator(".react-flow__node").first()
    const draggable = await firstNode.getAttribute("draggable")
    expect(draggable).not.toBe("true")

    // Cleanup
    await deleteTemplateFixture(request, templateId)
  })

  test("拖拽后点击节点仍显示属性面板", async ({ page }) => {
    const canvas = page.locator('[data-testid="dag-canvas"]').first()
    await expect(canvas).toBeVisible({ timeout: 5000 })

    const firstNode = canvas.locator(".react-flow__node").first()
    const box = await firstNode.boundingBox()
    expect(box).not.toBeNull()

    // Drag the node a small distance
    await dragNodeBy(page, firstNode, 100, 0)

    // Now click the node (not drag)
    await firstNode.click()
    await page.waitForTimeout(300)

    // Detail panel should appear
    const panel = page.locator('[data-testid="dag-detail-panel"]')
    await expect(panel).toBeVisible()
    await expect(panel.locator('[data-testid="canvas-edit-title"]')).toHaveValue("市场调研")
  })
})

// ── Canvas 节点定位 ─────────────────────────────────────────────────────

test.describe("DAG Canvas 节点定位", () => {
  test.beforeEach(async ({ page }) => {
    await goToBoss(page)
    await openCreateForm(page)
    await expect(dagEditor(page).getByText("2 节点", { exact: true })).toBeVisible()
  })

  test("选择节点后详情面板显示该节点属性", async ({ page }) => {
    const canvas = page.locator('[data-testid="dag-canvas"]').first()
    await expect(canvas).toBeVisible({ timeout: 5000 })

    const select = canvas.locator('[data-testid="canvas-locate-node-select"]')
    await expect(select).toBeVisible()

    // Select "marketing" node (title: "营销文案")
    await select.selectOption("marketing")
    await page.waitForTimeout(500)

    // Detail panel should show marketing node properties
    const panel = page.locator('[data-testid="dag-detail-panel"]')
    await expect(panel).toBeVisible()
    await expect(panel.locator('[data-testid="canvas-edit-title"]')).toHaveValue("营销文案")
    await expect(panel.locator('[data-testid="canvas-edit-agent_id"]')).toHaveValue("marketing")
  })

  test("选择节点后节点处于 selected 样式", async ({ page }) => {
    const canvas = page.locator('[data-testid="dag-canvas"]').first()
    await expect(canvas).toBeVisible({ timeout: 5000 })

    const select = canvas.locator('[data-testid="canvas-locate-node-select"]')
    await select.selectOption("marketing")
    await page.waitForTimeout(500)

    // The marketing node should have the selected ring style
    const marketingNode = canvas.locator(".react-flow__node").nth(1)
    await expect(marketingNode.locator(".ring-2")).toBeVisible()
  })

  test("只读预览不显示节点定位控件", async ({ page, request }) => {
    const templateId = await createTemplateFixture(request, "Canvas-只读定位测试")

    await goToBoss(page)

    // Expand the readonly canvas preview
    const previewBtn = page.locator('[data-testid="preview-canvas-btn"]').first()
    await expect(previewBtn).toBeVisible({ timeout: 10000 })
    await previewBtn.click()
    await page.waitForTimeout(500)

    const readonlyCanvas = page.locator('[data-testid="dag-canvas"]').first()
    await expect(readonlyCanvas).toBeVisible()

    // Locate dropdown should NOT exist in readonly canvas
    const locateSelect = readonlyCanvas.locator('[data-testid="canvas-locate-node-select"]')
    await expect(locateSelect).toHaveCount(0)

    // Cleanup
    await deleteTemplateFixture(request, templateId)
  })
})

// ── Canvas 小屏体验 ─────────────────────────────────────────────────────

test.describe("DAG Canvas 小屏体验", () => {
  test("小屏 viewport 下 Canvas 工具区可见且不遮挡第一个节点", async ({ page }) => {
    // Set a small viewport
    await page.setViewportSize({ width: 480, height: 800 })
    await goToBoss(page)
    await openCreateForm(page)
    await expect(dagEditor(page).getByText("2 节点", { exact: true })).toBeVisible()

    const canvas = page.locator('[data-testid="dag-canvas"]').first()
    await expect(canvas).toBeVisible({ timeout: 5000 })

    // Toolbar should be visible
    const addBtn = canvas.locator('[data-testid="canvas-add-node-btn"]')
    await expect(addBtn).toBeVisible()

    // First ReactFlow node should also be visible (not hidden behind toolbar)
    const firstNode = canvas.locator(".react-flow__node").first()
    await expect(firstNode).toBeVisible()

    // Verify the toolbar and node don't fully overlap
    const toolbarBox = await addBtn.boundingBox()
    const nodeBox = await firstNode.boundingBox()
    expect(toolbarBox).not.toBeNull()
    expect(nodeBox).not.toBeNull()

    // The node's top should be below the toolbar's bottom (with some tolerance)
    // OR they overlap by less than 20px (toolbar is small enough)
    const overlap = toolbarBox!.y + toolbarBox!.height - nodeBox!.y
    expect(overlap).toBeLessThan(30)

    // Restore default viewport
    await page.setViewportSize({ width: 1280, height: 720 })
  })

  test("小屏 viewport 下详情面板输入框没有水平溢出", async ({ page }) => {
    await page.setViewportSize({ width: 480, height: 800 })
    await goToBoss(page)
    await openCreateForm(page)
    await expect(dagEditor(page).getByText("2 节点", { exact: true })).toBeVisible()

    const canvas = page.locator('[data-testid="dag-canvas"]').first()
    await expect(canvas).toBeVisible({ timeout: 5000 })

    // Click a node to open detail panel
    const firstNode = canvas.locator(".react-flow__node").first()
    await firstNode.click()
    await page.waitForTimeout(300)

    const panel = page.locator('[data-testid="dag-detail-panel"]')
    await expect(panel).toBeVisible()

    // Check that the panel doesn't overflow the canvas width
    const canvasBox = await canvas.boundingBox()
    const panelBox = await panel.boundingBox()
    expect(canvasBox).not.toBeNull()
    expect(panelBox).not.toBeNull()

    // Panel should not extend beyond canvas right edge (with tolerance)
    expect(panelBox!.x + panelBox!.width).toBeLessThanOrEqual(canvasBox!.x + canvasBox!.width + 5)

    // Input fields should be visible and not overflow
    const titleInput = panel.locator('[data-testid="canvas-edit-title"]')
    await expect(titleInput).toBeVisible()
    const inputBox = await titleInput.boundingBox()
    expect(inputBox).not.toBeNull()
    // Input should fit within the panel
    expect(inputBox!.x + inputBox!.width).toBeLessThanOrEqual(panelBox!.x + panelBox!.width + 5)

    await page.setViewportSize({ width: 1280, height: 720 })
  })
})
