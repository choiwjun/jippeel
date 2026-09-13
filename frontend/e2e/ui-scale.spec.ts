import { type Page, type Route } from "@playwright/test";
import { expect, test } from "./coverage-test";

/**
 * U04 — 시니어 확대 모드 (화면 확대 배율) — fixture-only UI 검증.
 * 모든 /api/v1 트래픽은 이 파일의 인메모리 상태로 응답한다(미모킹 요청은 tripwire가 잡는다).
 */

let unhandled: string[] = [];

async function setupFixture(page: Page) {
  await page.context().route("**/api/v1/**", async (route: Route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace("/api/v1", "");
    const method = route.request().method();
    const json = (status: number, body: unknown) =>
      route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

    if (method === "GET" && path === "/projects") return json(200, []);
    if (method === "GET" && path === "/ai/presets") return json(200, []);
    if (method === "GET" && path === "/ai/usage") return json(200, []);
    if (method === "GET" && path === "/system/db-info")
      return json(200, { path: "fixture.db", size_bytes: 0, alembic_head: "test" });

    unhandled.push(`${method} ${path}`);
    return json(404, { detail: `unhandled fixture route: ${method} ${path}` });
  });
}

const uiScale = (page: Page) =>
  page.evaluate(() => document.documentElement.dataset.uiScale);

test.describe("U04 시니어 확대 모드", () => {
  test.beforeEach(() => {
    unhandled = [];
  });
  test.afterEach(() => {
    expect(unhandled, `unhandled fixture requests: ${unhandled.join(", ")}`).toEqual([]);
  });

  test("기본은 보통이고 크게/더 크게 선택이 즉시 루트에 반영된다", async ({ page }) => {
    await setupFixture(page);
    await page.goto("/settings");

    await page.getByRole("tab", { name: "테마" }).click();
    await expect(page.getByRole("radio", { name: "보통" })).toBeChecked();

    await page.getByRole("radio", { name: /더 크게/ }).check();
    await expect.poll(() => uiScale(page)).toBe("xlarge");
    await expect(page.getByRole("radio", { name: /더 크게/ })).toBeChecked();

    await page.getByRole("radio", { name: /크게 \(115%\)/ }).check();
    await expect.poll(() => uiScale(page)).toBe("large");
  });

  test("선택한 배율이 새로고침 후에도 유지된다", async ({ page }) => {
    await setupFixture(page);
    await page.goto("/settings");
    await page.getByRole("tab", { name: "테마" }).click();
    await page.getByRole("radio", { name: /크게 \(115%\)/ }).check();
    await expect.poll(() => uiScale(page)).toBe("large");

    await page.reload();
    await expect.poll(() => uiScale(page)).toBe("large");
    await page.getByRole("tab", { name: "테마" }).click();
    await expect(page.getByRole("radio", { name: /크게 \(115%\)/ })).toBeChecked();
  });

  test("보통으로 되돌리면 배율이 해제된다", async ({ page }) => {
    await setupFixture(page);
    await page.goto("/settings");
    await page.getByRole("tab", { name: "테마" }).click();
    await page.getByRole("radio", { name: /더 크게/ }).check();
    await expect.poll(() => uiScale(page)).toBe("xlarge");

    await page.getByRole("radio", { name: "보통" }).check();
    await expect.poll(() => uiScale(page)).toBe("normal");
  });
});
