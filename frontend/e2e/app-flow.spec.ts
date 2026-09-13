import { test, expect } from "@playwright/test";

/**
 * 종단 시나리오 (S1→S7) — 실구동 앱(:5173)+백엔드(:8000) 검증.
 *  S1 홈 프로젝트 생성 → S2 회차 생성·원고 타이핑·글자수 갱신
 *  → S5 AI 패널 스트리밍 + P1 자동삽입 금지 + 끼워넣기
 *  → S6 윤문 diff·게이트 + 거절 시 본문 불변
 *  → S7 고정 ChatGPT OAuth provider 안내와 credential 비저장 확인
 *  → 스크린샷 3장 + 테스트 프로젝트 API 삭제(정리).
 *
 * 상태 관리 — 테스트 블록 간 변수 공유 금지:
 *  projectId/chapterId는 beforeAll에서 API로 생성해 확정한다.
 *  UI 생성 흐름(S1)은 블록 내 지역 변수로만 다루고 블록 안에서 즉시 정리한다.
 */

const PROJECT_TITLE = "E2E테스트";
const FAKE_LLM_OUTPUT = "안녕하세요, 테스트응답입니다.";
const SHOT_DIR = "e2e/screenshots";

/** ~300자 한국어 원고 (공백 포함 322자) */
const MANUSCRIPT = [
  "깊은 숲 속 작은 오두막에는 이름 없는 소녀가 살고 있었다.",
  "소녀는 매일 아침 이슬 맺힌 허브를 따서 창가에 말렸고,",
  "저녁이면 벽난로 앞에서 낡은 일기장에 하루를 적었다.",
  "어느 겨울날 문을 두드린 낯선 여행자는 소녀의 일기를 읽고 말았다.",
  '"당신의 글은 사람 마음을 데워주는 태로군요." 여행자가 말했다.',
  "소녀는 처음으로 자신의 문장이 누군가에게 닿았다는 사실을 알았다.",
].join("\n");

async function getJson(
  request: import("@playwright/test").APIRequestContext,
  path: string,
) {
  const res = await request.get(path);
  expect(res.ok()).toBeTruthy();
  return res.json();
}

test.describe
  .serial("jippeel 종단 흐름", () => {
    let projectId = 0;
    let chapterId = 0;

    // [임시 계측] 콘솔/페이지에러/네트워크 실패 수집 — 실패한 테스트에 한해 출력
    test.beforeEach(async ({ page }, testInfo) => {
      const logs: string[] = [];
      page.on("console", (msg) =>
        logs.push(`[console.${msg.type()}] ${msg.text()}`),
      );
      page.on("pageerror", (err) =>
        logs.push(`[pageerror] ${err.message}\n${err.stack ?? ""}`),
      );
      page.on("requestfailed", (req) =>
        logs.push(
          `[requestfailed] ${req.method()} ${req.url()} :: ${req.failure()?.errorText}`,
        ),
      );
      page.on("response", (res) => {
        if (res.status() >= 400)
          logs.push(
            `[http ${res.status()}] ${res.request().method()} ${res.url()}`,
          );
      });
      (testInfo as unknown as { _diagLogs?: string[] })._diagLogs = logs;
    });
    test.afterEach(async ({}, testInfo) => {
      const logs = (testInfo as unknown as { _diagLogs?: string[] })._diagLogs;
      if (
        testInfo.status !== testInfo.expectedStatus &&
        logs &&
        logs.length > 0
      ) {
        // eslint-disable-next-line no-console
        console.log(
          `\n===== [${testInfo.title}] 진단 로그 (${logs.length}건) =====\n` +
            logs.join("\n") +
            "\n=========================================",
        );
      }
    });

    test.beforeAll(async ({ request }) => {
      // 기존 데이터 충돌 방지 — 동일 접두어 프로젝트 선제 삭제(전체 시나리오 시작 시 1회)
      const res = await request.get("/api/v1/projects");
      const projects = (await res.json()) as Array<{
        id: number;
        title: string;
      }>;
      for (const p of projects) {
        if (
          p.title === PROJECT_TITLE ||
          p.title.startsWith(`${PROJECT_TITLE}-`)
        ) {
          const del = await request.delete(`/api/v1/projects/${p.id}`);
          expect(del.ok()).toBeTruthy();
        }
      }

      // 프로젝트 생성(API) → projectId 확정
      const pres = await request.post("/api/v1/projects", {
        data: { title: PROJECT_TITLE },
      });
      expect(pres.ok()).toBeTruthy();
      projectId = ((await pres.json()) as { id: number }).id;
      expect(projectId).toBeGreaterThan(0);

      // 회차 생성(API, 빈 제목 → 사이드바 '{volume}권 {id}화' 표기) → chapterId 확정
      const cres = await request.post(
        `/api/v1/projects/${projectId}/chapters`,
        {
          data: { volume: 1, title: "", sort_order: 1 },
        },
      );
      expect(cres.ok()).toBeTruthy();
      chapterId = ((await cres.json()) as { id: number }).id;
      expect(chapterId).toBeGreaterThan(0);
    });

    test.afterAll(async ({ request }) => {
      // 정리 블록이 실패·미실행된 경우를 대비한 최후 정리(성공 시 no-op)
      if (projectId) await request.delete(`/api/v1/projects/${projectId}`);
    });

    test("S1 홈에서 프로젝트 생성 → 카드 노출", async ({ page }) => {
      // UI 생성 흐름 검증은 이 블록 안에서 자체 완결 — 공유 변수에 기록하지 않는다.
      const uiProjectTitle = `${PROJECT_TITLE}-UI생성`;

      await page.goto("/");
      await expect(
        page.getByRole("heading", { name: "내 프로젝트" }),
      ).toBeVisible();

      await page.getByRole("button", { name: "+ 새 작품" }).first().click();
      const dialog = page.getByRole("dialog");
      await dialog.getByPlaceholder("제목").fill(uiProjectTitle);
      await dialog.getByRole("button", { name: "생성" }).click();

      // 카드 노출 확인
      const card = page
        .locator("main .grid > div")
        .filter({ hasText: uiProjectTitle });
      await expect(card).toBeVisible();
      await expect(card.getByRole("heading")).toHaveText(uiProjectTitle);

      // 블록 내 정리 — 생성된 프로젝트를 목록 API로 조회해 즉시 삭제
      const res = await page.request.get("/api/v1/projects");
      const projects = (await res.json()) as Array<{
        id: number;
        title: string;
      }>;
      const created = projects.find((p) => p.title === uiProjectTitle);
      expect(created).toBeDefined();
      const del = await page.request.delete(`/api/v1/projects/${created!.id}`);
      expect(del.status()).toBe(204);
    });

    test('S2 진입 → 회차 진입("1화" 개명) → 300자 타이핑 → 공백제외 글자수 갱신', async ({
      page,
    }) => {
      await page.goto("/");
      const card = page
        .locator("main .grid > div")
        .filter({ hasText: PROJECT_TITLE });
      await card.getByRole("link", { name: /열기/ }).click();
      await expect(page).toHaveURL(new RegExp(`/projects/${projectId}/write`));

      // beforeAll에서 API 생성한 회차 — 사이드바 '{volume}권 {chapterId}화' 표기 확인 후 선택
      const sidebarBtn = page
        .locator("aside button")
        .filter({ hasText: new RegExp(`^1권 ${chapterId}화`) });
      await expect(sidebarBtn).toBeVisible();
      await sidebarBtn.click();

      const titleInput = page.locator('input[placeholder="회차 제목"]');
      await titleInput.fill("1화");
      await titleInput.blur();
      await expect(
        page.locator("aside button").filter({ hasText: /^1화/ }),
      ).toBeVisible({ timeout: 15_000 });

      // 에디터 타이핑(CodeMirror contenteditable) + 초기 카운터 0 확인
      const editor = page.locator(".cm-content");
      await expect(editor).toBeVisible();
      const counterNoSpace = page.locator("span", { hasText: /^공백제외/ });
      await expect(counterNoSpace).toContainText("공백제외 0");

      await editor.click();
      await editor.fill(MANUSCRIPT);

      // FR-104 — 200ms 디바운스 후 공백제외 글자수 갱신 확인
      const expectedNoSpace = MANUSCRIPT.replace(/\s/g, "").length;
      await expect(counterNoSpace).toHaveText(
        `공백제외 ${expectedNoSpace.toLocaleString("ko-KR")}`,
        { timeout: 10_000 },
      );

      // FR-106 자동저장(1.5s 디바운스) 대기 후 본문 저장 확인
      await expect
        .poll(
          async () => {
            const ch = (await getJson(
              page.request,
              `/api/v1/chapters/${chapterId}`,
            )) as {
              content_md: string;
            };
            return ch.content_md;
          },
          { timeout: 20_000 },
        )
        .toBe(MANUSCRIPT);

      await page.screenshot({
        path: `${SHOT_DIR}/02-editor-typing.png`,
        fullPage: false,
      });
    });

    test("S5 AI 패널 스트리밍 → P1 자동삽입 금지 → 끼워넣기 반영", async ({
      page,
    }) => {
      await page.goto(`/projects/${projectId}/write`);
      const editor = page.locator(".cm-content");
      await expect(editor).toBeVisible();

      // 본문 기준점 확보 (자동저장 플러시 대기)
      await expect
        .poll(
          async () =>
            (
              (await getJson(
                page.request,
                `/api/v1/chapters/${chapterId}`,
              )) as { content_md: string }
            ).content_md,
        )
        .toBe(MANUSCRIPT);

      await page.getByRole("button", { name: "AI 패널" }).click();
      await expect(
        page.getByText("AI 결과는 자동으로 본문에 들어가지 않습니다."),
      ).toBeVisible();

      // 실제 provider를 호출하지 않고 browser route로 SSE 계약만 고정한다.
      await page.route("**/api/v1/ai/generate", async (route) => {
        const body = [
          "event: start\ndata: " +
            JSON.stringify({
              model: "gpt-5.6-luna",
              injected_lore: [],
              injected_foreshadows: [],
              injected_outline: null,
              review_enabled: false,
            }) +
            "\n\n",
          "event: message\ndata: " +
            JSON.stringify({ delta: FAKE_LLM_OUTPUT }) +
            "\n\n",
          "event: done\ndata: [DONE]\n\n",
        ].join("");
        await route.fulfill({
          status: 200,
          headers: { "content-type": "text/event-stream" },
          body,
        });
      });

      // 프롬프트 직접 입력 → 생성
      await page
        .getByLabel("프롬프트 직접 입력")
        .fill("이어서 한 문단 집필해줘.");
      await page.getByRole("button", { name: /생성 시작/ }).click();
      // 스트림 개시(중단 버튼) 또는 즉시 완료(응답 수신) 둘 중 하나면 통과 — fake LLM은 즉완 가능
      const resultPre = page
        .locator("pre")
        .filter({ hasText: FAKE_LLM_OUTPUT });
      await expect(
        page.getByRole("button", { name: /중단/ }).or(resultPre),
      ).toBeVisible({ timeout: 30_000 });
      await expect(
        page.getByRole("button", { name: /생성 시작/ }),
      ).toBeVisible(); // done 복귀

      // P1(FR-406) — 결과가 본문에 자동 삽입되지 않았음을 단언
      const contentAfterStream = (
        (await getJson(page.request, `/api/v1/chapters/${chapterId}`)) as {
          content_md: string;
        }
      ).content_md;
      expect(contentAfterStream).not.toContain(FAKE_LLM_OUTPUT);
      expect(contentAfterStream).toBe(MANUSCRIPT);
      await expect(editor).not.toContainText(FAKE_LLM_OUTPUT);

      await page.screenshot({
        path: `${SHOT_DIR}/03-ai-panel-result.png`,
        fullPage: false,
      });

      // [끼워넣기] — 명시 클릭 시에만 본문 반영(P1 유일 경로)
      await page.getByRole("button", { name: /끼워넣기/ }).click();
      await expect(editor).toContainText(FAKE_LLM_OUTPUT);
      await expect
        .poll(
          async () =>
            (
              (await getJson(
                page.request,
                `/api/v1/chapters/${chapterId}`,
              )) as { content_md: string }
            ).content_md,
          { timeout: 20_000 },
        )
        .toContain(FAKE_LLM_OUTPUT);
    });

    test("S6 윤문 실행 → diff·게이트 렌더 → 거절 시 본문 불변", async ({
      page,
    }) => {
      await page.goto(`/projects/${projectId}/write`);
      const editor = page.locator(".cm-content");
      await expect(editor).toBeVisible();

      const beforeRefine = (
        (await getJson(page.request, `/api/v1/chapters/${chapterId}`)) as {
          content_md: string;
        }
      ).content_md;

      await page.getByRole("button", { name: "윤문 리포트" }).click();
      await expect(
        page.getByRole("heading", { name: "윤문 리포트" }),
      ).toBeVisible();
      await page.route("**/api/v1/refine", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            run_id: 999,
            base_revision: 0,
            route_hint: "standard",
            spans: [
              {
                category: "E",
                start: 0,
                end: 5,
                severity: "info",
                message: "리듬 점검",
              },
            ],
            original: MANUSCRIPT,
            refined: `${MANUSCRIPT}\n다듬은 문장.`,
            changed_ratio: 0.1,
            gate: "pass",
            status: "ok",
          }),
        });
      });
      await page.route("**/api/v1/refine/runs/*/reject", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: "{}",
        });
      });
      await page.getByRole("button", { name: /🔍 윤문 실행/ }).click();

      // diff 병렬 뷰 + 변경률 게이트 UI(30% 경고 / 50% 차단 눈금) 렌더 확인
      await expect(
        page.getByText("변경률 게이트 — 30% 경고 / 50% 차단"),
      ).toBeVisible();
      await expect(page.getByText("30% 경고", { exact: true })).toBeVisible();
      await expect(page.getByText("50% 차단", { exact: true })).toBeVisible();
      await expect(page.getByLabel("원문 비교 보기")).toBeVisible();
      await expect(
        page.getByLabel(/수정본 비교 보기|진단 하이라이트/),
      ).toBeVisible();
      await expect(page.getByText(/진단 \d+건/)).toBeVisible();

      await page.screenshot({
        path: `${SHOT_DIR}/04-refine-report.png`,
        fullPage: false,
      });

      // 거절(C-2 block 게이트면 [폐기]) — 어느 쪽이든 본문 불변
      await page.getByRole("button", { name: /✗ 거절|🗑 폐기/ }).click();
      await expect(page.getByText("윤문 파이프라인 실행 중…")).toBeHidden();
      await expect(page.getByLabel("윤문 강도")).toBeVisible({
        timeout: 15_000,
      }); // 리포트 닫힘 → 재실행 화면

      const afterReject = (
        (await getJson(page.request, `/api/v1/chapters/${chapterId}`)) as {
          content_md: string;
        }
      ).content_md;
      expect(afterReject).toBe(beforeRefine);
      await expect(editor).toContainText(FAKE_LLM_OUTPUT); // 화면 본문도 불변
    });

    test("S7 설정 — 고정 ChatGPT OAuth provider와 credential 비저장 안내", async ({
      page,
    }) => {
      await page.goto("/settings");
      await expect(
        page.getByRole("heading", { name: /설정/ }).first(),
      ).toBeVisible();
      await expect(page.getByRole("tab", { name: "GPT OAuth" })).toBeVisible();
      await expect(
        page.getByRole("heading", { name: "ChatGPT OAuth 연결" }),
      ).toBeVisible();
      await expect(
        page.getByText("gpt-5.6-luna", { exact: true }),
      ).toBeVisible();
      await expect(
        page.getByText(
          /API key나 사용자 지정 모델 서버 설정을 이 앱에 저장하지 않습니다/,
        ),
      ).toBeVisible();

      // 현재 설정 화면에는 endpoint/API key/server URL 입력·표시가 없다.
      await expect(page.getByLabel(/엔드포인트|API key|서버 주소/)).toHaveCount(
        0,
      );
      await expect(page.getByRole("button", { name: /표시/ })).toHaveCount(0);

      await page.screenshot({
        path: `${SHOT_DIR}/05-settings-gpt-oauth.png`,
        fullPage: true,
      });
    });

    test("TC-038 근사 — 입력 직후 이탈 시 keepalive PUT 플러시로 원고 보존", async ({
      page,
    }) => {
      // 시나리오: 자동저장 디바운스(1.5초)가 끝나기 전에 페이지를 떠나면
      // 언로드 플러시(fetch keepalive PUT)가 남은 변경을 저장해야 한다.
      await page.goto(`/projects/${projectId}/write`);
      const editor = page.locator(".cm-content");
      await expect(editor).toBeVisible();

      const before = (
        (await getJson(page.request, `/api/v1/chapters/${chapterId}`)) as {
          content_md: string;
        }
      ).content_md;

      const EXTRA = " 이탈 플러시 검증 문장.";
      // fill로 변경(키보드 입력과 동일하게 onChange → dirty 트리거) 후
      // 1.5초 자동저장 대기 없이 즉시 이탈 — 언로드 플러시가 저장을 담당해야 한다
      await editor.fill(before + EXTRA);
      await page.goto("/");

      await expect
        .poll(
          async () =>
            (
              (await getJson(
                page.request,
                `/api/v1/chapters/${chapterId}`,
              )) as { content_md: string }
            ).content_md,
          { timeout: 10_000 },
        )
        .toContain(EXTRA.trim());
      // 이탈 전 본문이 유실되지 않았는지도 확인
      const after = (
        (await getJson(page.request, `/api/v1/chapters/${chapterId}`)) as {
          content_md: string;
        }
      ).content_md;
      expect(after.startsWith(before)).toBeTruthy();
    });

    test("TC-308 — 미리보기 XSS 차단(script 실행·onerror 속성 없음)", async ({
      page,
    }) => {
      // 전용 검증 회차를 만들어 원본 본문과 분리한다
      const xres = await page.request.post(
        `/api/v1/projects/${projectId}/chapters`,
        {
          data: { volume: 1, title: "XSS검증", sort_order: 999 },
        },
      );
      const xssChapterId = ((await xres.json()) as { id: number }).id;
      const PAYLOAD =
        '<script>window.__xss=1</script><img src=x onerror="window.__xss=2">**굵게**';
      // 본문을 먼저 저장해두어야 에디터가 XSS 내용을 로드한 상태로 미리보기에 들어간다
      await page.request.put(`/api/v1/chapters/${xssChapterId}/content`, {
        data: { content_md: PAYLOAD, expected_revision: 0 },
      });

      await page.goto(`/projects/${projectId}/write`);
      const xssBtn = page
        .locator("aside button")
        .filter({ hasText: "XSS검증" });
      await expect(xssBtn).toBeVisible({ timeout: 15_000 });
      await xssBtn.click();
      const editor = page.locator(".cm-content");
      await expect(editor).toContainText("굵게", { timeout: 15_000 });
      await page.getByRole("tab", { name: "미리보기" }).click();

      const preview = page.locator("main");
      // 스크립트 요소가 실제로 생성되지 않고, onerror 속성도 살아있지 않아야 한다
      expect(await preview.locator("script").count()).toBe(0);
      expect(await preview.locator("img[onerror]").count()).toBe(0);
      expect(
        await page.evaluate(() => (window as { __xss?: number }).__xss),
      ).toBeUndefined();
      // 마크다운 렌더링은 정상 동작
      await expect(preview.getByText("굵게")).toBeVisible();

      await page.request.delete(`/api/v1/chapters/${xssChapterId}`);
    });

    test("정리 — 테스트 프로젝트 API 삭제", async ({ request }) => {
      test.skip(!projectId, "생성된 프로젝트 없음");
      const res = await request.delete(`/api/v1/projects/${projectId}`);
      expect(res.status()).toBe(204);
      projectId = 0; // afterAll 중복 삭제 방지
    });
  });
