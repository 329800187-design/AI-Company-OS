import { expect, test } from "@playwright/test"

test("Agent 控制台可运行并展示本地浏览器验收结果", async ({ page }) => {
  await page.route("**/agent-console/discovered", route => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ agents: [], total: 0, enabled_count: 0 }),
  }))
  await page.route("**/browser-verification/runs", route => {
    if (route.request().method() === "POST") {
      return route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          run_id: "browser_verify_e2e",
          status: "passed",
          started_at: "2026-08-26T00:00:00+00:00",
          finished_at: "2026-08-26T00:00:01+00:00",
          targets: ["http://127.0.0.1:8000/health", "http://127.0.0.1:5173/app"],
          checks: [
            { id: "backend_health", target: "http://127.0.0.1:8000/health", passed: true, message: "后端健康检查通过" },
            { id: "frontend_page", target: "http://127.0.0.1:5173/app", passed: true, message: "前端页面加载通过" },
          ],
          passed_count: 2,
          total_count: 2,
        }),
      })
    }
    return route.fulfill({ contentType: "application/json", body: JSON.stringify({ runs: [] }) })
  })

  await page.goto("/app?page=agent-console")
  await expect(page.getByRole("heading", { name: "Agent 控制台" })).toBeVisible()
  await page.getByTestId("browser-verification-run-button").click()
  await expect(page.getByTestId("browser-verification-result")).toContainText("验收通过")
  await expect(page.getByTestId("browser-verification-result")).toContainText("2 / 2")
})
