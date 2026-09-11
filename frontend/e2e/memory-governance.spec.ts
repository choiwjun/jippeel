import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const now = "2026-09-11T00:00:00.000Z";

test("작품별 장편 기억을 추가·승인하고 stale 경고를 표시한다", async ({
  page,
}) => {
  let nextId = 1;
  const memories = [
    {
      id: nextId++,
      project_id: 1,
      chapter_id: 10,
      source_revision: 3,
      source_sha256: "a".repeat(64),
      kind: "fact",
      body: "현재 원문과 연결된 기억",
      visibility: "approved",
      effective_from_sort_order: null,
      effective_to_sort_order: null,
      provenance: { source: "manual" },
      created_at: now,
      updated_at: now,
      stale: true,
      source_chapter_title: "1화",
      source_chapter_revision: 4,
      source_chapter_sort_order: 1,
    },
  ];

  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace("/api/v1", "");
    const json = (status: number, body: unknown) =>
      route.fulfill({
        status,
        contentType: "application/json",
        body: JSON.stringify(body),
      });

    if (request.method() === "GET" && path === "/projects/1") {
      return json(200, {
        id: 1,
        title: "테스트 작품",
        genre: "판타지",
        synopsis: "작품 설명",
        platform_note: null,
        created_at: now,
        updated_at: now,
      });
    }
    if (request.method() === "GET" && path === "/projects/1/chapters") {
      return json(200, [
        {
          id: 10,
          project_id: 1,
          volume: null,
          sort_order: 1,
          title: "1화",
          status: "초고",
          word_count_cache: 0,
          memo: null,
          revision: 4,
          created_at: now,
          updated_at: now,
        },
      ]);
    }
    if (request.method() === "GET" && path === "/projects/1/memories")
      return json(200, memories);
    if (request.method() === "POST" && path === "/projects/1/memories") {
      const body = JSON.parse(request.postData() ?? "{}");
      const created = {
        ...memories[0],
        id: nextId++,
        body: body.body,
        kind: body.kind,
        visibility: "draft",
        stale: false,
        source_revision: 4,
        source_chapter_revision: 4,
      };
      memories.push(created);
      return json(201, created);
    }
    const updateMatch = path.match(/^\/projects\/1\/memories\/(\d+)$/);
    if (request.method() === "PATCH" && updateMatch) {
      const target = memories.find(
        (memory) => memory.id === Number(updateMatch[1]),
      );
      if (!target) return json(404, { detail: "memory not found" });
      Object.assign(target, JSON.parse(request.postData() ?? "{}"));
      return json(200, target);
    }
    return json(404, { detail: "fixture route not found" });
  });

  await page.goto("/projects/1/memory");
  await expect(page.getByRole("heading", { name: "장편 기억" })).toBeVisible();
  await expect(page.getByText("stale — 자동 주입 제외")).toBeVisible();
  await expect(
    page.getByText("원문 revision/hash가 달라져 자동 주입하지 않습니다."),
  ).toBeVisible();

  await page.getByLabel("내용").fill("새로 확인한 인물의 결정");
  await page.getByRole("button", { name: "초안 추가" }).click();
  await expect(page.getByText("새로 확인한 인물의 결정")).toBeVisible();

  const draft = page
    .locator("article")
    .filter({ hasText: "새로 확인한 인물의 결정" });
  await draft.getByRole("button", { name: "승인" }).click();
  await expect(draft.getByText("상태를 변경할까요?")).toBeVisible();
  await expect(draft.getByRole("button", { name: "확인" })).toBeFocused();
  await draft.getByRole("button", { name: "확인" }).click();
  await expect(draft.getByText("승인")).toBeVisible();

  await page.getByLabel("기억 상태 필터").selectOption("approved");
  await expect(page.getByText("새로 확인한 인물의 결정")).toBeVisible();

  const accessibilityScan = await new AxeBuilder({ page }).analyze();
  expect(
    accessibilityScan.violations.filter(
      (violation) =>
        violation.impact === "critical" || violation.impact === "serious",
    ),
  ).toHaveLength(0);
});
