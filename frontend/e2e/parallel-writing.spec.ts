import { test, expect } from "@playwright/test";

const PROJECT_TITLE = "병렬집필E2E";

function sse(events: Array<[string, unknown | string]>): string {
  return events
    .map(
      ([event, data]) =>
        `event: ${event}\ndata: ${typeof data === "string" ? data : JSON.stringify(data)}\n\n`,
    )
    .join("");
}

test.describe
  .serial("병렬 집필 AI 패널", () => {
    let projectId = 0;
    let chapterId = 0;

    test.beforeAll(async ({ request }) => {
      const existing = await request.get("/api/v1/projects");
      for (const project of (await existing.json()) as Array<{
        id: number;
        title: string;
      }>) {
        if (project.title === PROJECT_TITLE)
          await request.delete(`/api/v1/projects/${project.id}`);
      }
      const projectResponse = await request.post("/api/v1/projects", {
        data: { title: PROJECT_TITLE },
      });
      expect(projectResponse.ok()).toBeTruthy();
      projectId = ((await projectResponse.json()) as { id: number }).id;
      const chapterResponse = await request.post(
        `/api/v1/projects/${projectId}/chapters`,
        {
          data: { volume: 1, title: "병렬 테스트", sort_order: 1 },
        },
      );
      expect(chapterResponse.ok()).toBeTruthy();
      chapterId = ((await chapterResponse.json()) as { id: number }).id;
    });

    test.afterAll(async ({ request }) => {
      if (projectId) await request.delete(`/api/v1/projects/${projectId}`);
    });

    test("parallel mode sends settings, renders draft/review, and does not auto-write", async ({
      page,
    }) => {
      const requests: Array<Record<string, unknown>> = [];
      await page.route("**/api/v1/ai/generate-parallel", async (route) => {
        requests.push(
          JSON.parse(route.request().postData() ?? "{}") as Record<
            string,
            unknown
          >,
        );
        const body = sse([
          [
            "parallel_start",
            {
              model: "gpt-5.6-luna",
              generation_reasoning_effort: "medium",
              review_model: "gpt-5.6-luna",
              review_reasoning_effort: "xhigh",
              worker_limit: 2,
              injected_lore: [],
              injected_foreshadows: [],
              injected_outline: null,
            },
          ],
          [
            "planner_done",
            {
              scene_count: 2,
              scenes: [
                { order: 1, title: "장면 1" },
                { order: 2, title: "장면 2" },
              ],
            },
          ],
          ["worker_start", { order: 1, title: "장면 1" }],
          ["worker_start", { order: 2, title: "장면 2" }],
          ["worker_done", { order: 1, title: "장면 1", chars: 20 }],
          ["worker_done", { order: 2, title: "장면 2", chars: 20 }],
          ["message", { delta: "병렬 초안 원고" }],
          [
            "review_start",
            {
              model: "gpt-5.6-luna",
              reasoning_effort: "xhigh",
            },
          ],
          ["review", { delta: "[감수]\n- 장면 전환을 확인했다." }],
          ["done", "[DONE]"],
        ]);
        await route.fulfill({
          status: 200,
          headers: { "content-type": "text/event-stream" },
          body,
        });
      });

      await page.goto(`/projects/${projectId}/write`);
      await expect(page.locator(".cm-content")).toBeVisible();
      await page.getByRole("button", { name: "AI 패널" }).click();
      await expect(page.getByText("생성 엔진")).toBeVisible();
      await page.getByLabel("집필 모드").selectOption("parallel");
      await page.locator("#ai-worker-limit").fill("2");
      await page.locator("#ai-parallel-review-effort").selectOption("xhigh");
      await page
        .getByLabel("프롬프트 직접 입력")
        .fill("두 장면으로 짧게 작성하라.");
      await page.getByRole("button", { name: "✨ 병렬 집필 시작" }).click();

      await expect(page.getByRole("tab", { name: /감수 의견/ })).toBeVisible({
        timeout: 15_000,
      });
      await expect(page.locator("pre")).toContainText("[감수]");
      await expect(page.locator("pre")).toContainText("장면 전환을 확인했다");
      await expect(
        page.locator("button", { hasText: "끼워넣기" }),
      ).toBeVisible();

      const chapter = await page.request.get(`/api/v1/chapters/${chapterId}`);
      expect(
        ((await chapter.json()) as { content_md: string }).content_md,
      ).toBe("");
      expect(requests).toHaveLength(1);
      expect(requests[0].worker_limit).toBe(2);
      expect(requests[0].preset_id).toBeNull();
      expect(
        (requests[0].review as { reasoning_effort: string }).reasoning_effort,
      ).toBe("xhigh");
    });
  });
