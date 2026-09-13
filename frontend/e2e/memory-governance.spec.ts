import AxeBuilder from "@axe-core/playwright";
import { expect } from "@playwright/test";
import { test } from "./memory-scoped-coverage";

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

  await page.context().route("**/api/v1/**", async (route) => {
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
  await expect(draft.getByText("이 기억을 승인할까요? 조건에 맞으면 AI 집필에 참고됩니다.")).toBeVisible();
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

// All network traffic stays inside this fixture; no backend/provider is started.
async function mockMemoryPage(page: import("@playwright/test").Page, visibility = "draft", navigate = true) {
  let memory = {
    id: 1, project_id: 1, chapter_id: null, source_revision: null,
    source_sha256: "a".repeat(64), kind: "fact", body: "검토 대상 기억", visibility,
    effective_from_sort_order: null, effective_to_sort_order: null,
    provenance: { source: "manual" }, created_at: now, updated_at: now,
    stale: false, source_chapter_title: null, source_chapter_revision: null,
    source_chapter_sort_order: null,
  };
  await page.context().route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    const json = (body: unknown) => route.fulfill({ json: body });
    if (path === "/projects/1") return json({ id: 1, title: "테스트 작품", genre: "판타지", synopsis: "설명", platform_note: null, created_at: now, updated_at: now });
    if (path === "/projects/1/chapters") return json([{ id: 10, project_id: 1, volume: null, title: "1화", sort_order: 1, status: "초고", word_count_cache: 0, memo: null, revision: 4, created_at: now, updated_at: now }]);
    if (path === "/projects/1/memories") {
      const filter = new URL(route.request().url()).searchParams.get("visibility");
      return json(!filter || filter === memory.visibility ? [memory] : []);
    }
    if (path === "/projects/1/memories/1" && route.request().method() === "PATCH") {
      memory = { ...memory, ...route.request().postDataJSON() };
      return json(memory);
    }
    return route.fulfill({ status: 404, json: { detail: "fixture only" } });
  });
  if (navigate) {
    await page.goto("/projects/1/memory");
    await expect(page.getByRole("heading", { name: "장편 기억", exact: true })).toBeVisible();
  }
}

for (const scenario of [
  { initial: "draft", action: "승인", target: "approved" },
  { initial: "draft", action: "폐기", target: "retired" },
  { initial: "approved", action: "폐기", target: "retired" },
]) {
  test(`${scenario.initial} ${scenario.action} sends the selected visibility`, async ({ page }) => {
    await mockMemoryPage(page, scenario.initial);
    const card = page.locator("article").filter({ hasText: "검토 대상 기억" });
    await card.getByRole("button", { name: scenario.action, exact: true }).click();
    await expect(card.getByText(scenario.target === "approved"
      ? "이 기억을 승인할까요? 조건에 맞으면 AI 집필에 참고됩니다."
      : "이 기억을 폐기할까요? AI 집필에 참고하지 않으며 다시 활성화할 수 없습니다.")).toBeVisible();
    await expect(card.getByRole("button", { name: "확인", exact: true })).toBeFocused();
    const request = page.waitForRequest((req) => req.method() === "PATCH");
    await card.getByRole("button", { name: "확인", exact: true }).click();
    expect((await request).postDataJSON()).toEqual({ visibility: scenario.target });
    await expect(card.locator("span.font-semibold")).toHaveText(scenario.action);
    if (scenario.target === "retired") {
      await expect(card.getByRole("button", { name: "승인", exact: true })).toHaveCount(0);
      await expect(card.getByRole("button", { name: "폐기", exact: true })).toHaveCount(0);
    }
  });
}

for (const succeeds of [true, false]) {
  test(`pending creation protects all inputs and ${succeeds ? "clears on success" : "preserves on failure"}`, async ({ page }) => {
    await mockMemoryPage(page);
    let release!: () => void;
    const gate = new Promise<void>((resolve) => { release = resolve; });
    let posted!: () => void;
    const started = new Promise<void>((resolve) => { posted = resolve; });
    let posts = 0;
    await page.route("**/api/v1/projects/1/memories", async (route) => {
      if (route.request().method() !== "POST") return route.fallback();
      posts += 1;
      posted();
      await gate;
      return route.fulfill({ status: succeeds ? 201 : 500, json: succeeds ? { id: 2 } : { detail: "저장 실패" } });
    });
    const fields = ["종류", "근거 회차(선택)", "내용", "적용 시작 sort order", "적용 종료 sort order"];
    await page.getByLabel("종류", { exact: true }).selectOption("summary");
    await page.getByLabel("근거 회차(선택)").selectOption("10");
    await page.getByLabel("내용", { exact: true }).fill("보존할 입력 A");
    await page.getByLabel("적용 시작 sort order").fill("1");
    await page.getByLabel("적용 종료 sort order").fill("5");
    await page.getByRole("button", { name: "초안 추가", exact: true }).focus();
    await page.keyboard.press("Enter");
    await started;
    try {
      for (const name of fields) await expect(page.getByLabel(name, { exact: true })).toBeDisabled();
      // Disabled controls cannot regain keyboard focus or accept input/activation.
      for (const name of fields) {
        const field = page.getByLabel(name, { exact: true });
        await field.evaluate((element: HTMLElement) => element.focus());
        await expect(field).not.toBeFocused();
      }
      await page.keyboard.type("B");
      const pendingButton = page.getByRole("button", { name: "추가 중…", exact: true });
      await expect(pendingButton).toBeDisabled();
      await pendingButton.evaluate((element: HTMLElement) => element.focus());
      await page.keyboard.press("Enter");
      await expect(page.getByLabel("내용", { exact: true })).toHaveValue("보존할 입력 A");
      expect(posts).toBe(1);
    } finally {
      release();
    }
    for (const name of fields) await expect(page.getByLabel(name, { exact: true })).toBeEnabled();
    await expect(page.getByLabel("내용", { exact: true })).toHaveValue(succeeds ? "" : "보존할 입력 A");
    await expect(page.getByLabel("근거 회차(선택)")).toHaveValue(succeeds ? "" : "10");
    await expect(page.getByLabel("적용 시작 sort order")).toHaveValue(succeeds ? "" : "1");
    await expect(page.getByLabel("적용 종료 sort order")).toHaveValue(succeeds ? "" : "5");
    await expect(page.getByLabel("종류", { exact: true })).toHaveValue("summary");
    if (!succeeds) {
      await expect(page.getByText(/기억 추가 실패/)).toBeVisible();
      await page.getByLabel("내용", { exact: true }).fill("실패 후 편집 가능");
    }
  });
}

// BrowserRouter handles popstate without replacing the document or QueryClient.
async function switchMemoryProject(page: import("@playwright/test").Page, pid: number) {
  await page.evaluate((id) => {
    history.pushState({}, "", `/projects/${id}/memory`);
    dispatchEvent(new PopStateEvent("popstate"));
  }, pid);
  await expect(page).toHaveURL(new RegExp(`/projects/${pid}/memory$`));
}

for (const method of ["POST", "PATCH"]) {
  for (const succeeds of [true, false]) {
    for (const returnToOrigin of [false, true]) {
      test(`M01 ${method} ${succeeds ? "success" : "error"} after SPA A-B${returnToOrigin ? "-A" : ""} isolates the screen`, async ({ page }) => {
        await mockMemoryPage(page);
        const reads: number[] = [];
        await page.route("**/api/v1/projects/*/**", async (route) => {
          const path = new URL(route.request().url()).pathname;
          const pid = Number(path.match(/projects\/(\d+)/)?.[1]);
          if (route.request().method() === "GET" && path.endsWith("/memories")) reads.push(pid);
          if (pid !== 2) return route.fallback();
          if (path.endsWith("/chapters")) return route.fulfill({ json: [] });
          if (path.endsWith("/memories")) return route.fulfill({ json: [] });
          return route.fulfill({ status: 404, json: { detail: "fixture only" } });
        });
        await page.route("**/api/v1/projects/2", (route) => route.fulfill({ json: { id: 2, title: "작품 B" } }));
        let release!: () => void;
        const gate = new Promise<void>((resolve) => { release = resolve; });
        const requestReady = page.waitForRequest((req) => req.method() === method);
        await page.route("**/api/v1/projects/1/memories**", async (route) => {
          if (route.request().method() !== method) return route.fallback();
          await gate;
          return route.fulfill({ status: succeeds ? 200 : 500, json: succeeds ? { id: 1 } : { detail: "delayed failure" } });
        });
        await page.getByLabel("내용", { exact: true }).fill("origin A body");
        await page.getByLabel("기억 종류 필터").selectOption("fact");
        if (method === "POST") await page.getByRole("button", { name: "초안 추가", exact: true }).click();
        else {
          await page.getByRole("button", { name: "승인", exact: true }).click();
          await page.getByRole("button", { name: "확인", exact: true }).click();
        }
        const request = await requestReady;
        expect(new URL(request.url()).pathname).toBe(`/api/v1/projects/1/memories${method === "PATCH" ? "/1" : ""}`);
        expect(request.postDataJSON()).toEqual(method === "POST" ? {
          kind: "fact", body: "origin A body", chapter_id: null,
          effective_from_sort_order: null, effective_to_sort_order: null,
        } : { visibility: "approved" });
        try {
          await switchMemoryProject(page, 2);
          await expect(page.getByLabel("내용", { exact: true })).toHaveValue("");
          await expect(page.getByLabel("기억 종류 필터")).toHaveValue("");
          await expect(page.getByRole("group", { name: "장편 기억 상태 변경 확인" })).toHaveCount(0);
          await expect.poll(() => reads.filter((id) => id === 2).length).toBe(1);
          if (returnToOrigin) {
            await switchMemoryProject(page, 1);
            await expect(page.getByLabel("내용", { exact: true })).toHaveValue("");
            await page.getByRole("button", { name: "폐기", exact: true }).click();
          }
          await page.getByLabel("내용", { exact: true }).fill("new screen body");
          const beforeOriginReads = reads.filter((id) => id === 1).length;
          const response = page.waitForResponse((res) => res.request() === request);
          release();
          await response;
          if (succeeds && returnToOrigin) await expect.poll(() => reads.filter((id) => id === 1).length).toBe(beforeOriginReads + 1);
          // Wait past React Query's notification batch, then inspect every current-screen effect.
          await page.waitForTimeout(150);
          await expect(page.getByLabel("내용", { exact: true })).toHaveValue("new screen body");
          await expect(page.getByLabel("내용", { exact: true })).toBeEnabled();
          await expect(page.getByLabel("내용", { exact: true })).toBeFocused();
          await expect(page.getByRole("button", { name: "초안 추가", exact: true })).toBeEnabled();
          await expect(page.getByRole("group", { name: "장편 기억 상태 변경 확인" })).toHaveCount(returnToOrigin ? 1 : 0);
          await expect(page.getByText(/장편 기억 초안을 추가했습니다|장편 기억 상태를 변경했습니다|기억 추가 실패|기억 상태 변경 실패/)).toHaveCount(0);
          expect(reads.filter((id) => id === 2)).toHaveLength(1);
          if (!returnToOrigin) {
            await switchMemoryProject(page, 1);
            await page.waitForTimeout(150);
          }
          expect(reads.filter((id) => id === 1)).toHaveLength(beforeOriginReads + (succeeds ? 1 : 0));
        } finally { release(); }
      });
    }
  }
}

for (const resource of [
  { path: "/projects/1", label: "작품 정보" },
  { path: "/projects/1/chapters", label: "근거 회차 목록" },
  { path: "/projects/1/memories", label: "기억 목록" },
]) {
  for (const refetch of [false, true]) {
    test(`M03 ${resource.label} ${refetch ? "refetch" : "initial"} failure retries without losing input`, async ({ page }) => {
      await mockMemoryPage(page, "draft", false);
      await page.clock.install();
      let failing = !refetch;
      let failures = 0;
      await page.route(`**/api/v1${resource.path}`, (route) => {
        if (!failing) return route.fallback();
        failures += 1;
        return route.fulfill({ status: 500, json: { detail: "fixture resource error" } });
      });
      await page.goto("/projects/1/memory");
      await page.getByLabel("내용", { exact: true }).fill("retry keeps manuscript-related note");
      if (refetch) {
        await expect(page.getByText("검토 대상 기억", { exact: true })).toBeVisible();
        await expect(page.getByText("작품: 테스트 작품", { exact: true })).toBeVisible();
        await expect(page.getByLabel("근거 회차(선택)").locator("option")).toHaveCount(2);
        failing = true;
        await page.clock.fastForward(31_000);
        await page.evaluate(() => { dispatchEvent(new Event("offline")); dispatchEvent(new Event("online")); });
      }
      const alert = page.getByRole("alert").filter({ hasText: `${resource.label}${resource.label === "작품 정보" ? "를" : "을"} 불러오지 못했습니다.` });
      await expect(alert).toBeVisible();
      expect(failures).toBe(2); // existing configured retry, then explicit recovery below
      await expect(page.getByText("조건에 맞는 장편 기억이 없습니다.", { exact: true })).toHaveCount(0);
      if (resource.label === "작품 정보") await expect(page.getByText(/작품: 불러오는 중/)).toHaveCount(0);
      if (refetch) {
        await expect(page.getByText("검토 대상 기억", { exact: true })).toBeVisible();
        await expect(page.getByLabel("근거 회차(선택)").locator("option")).toHaveCount(2);
      }
      failing = false;
      const retry = alert.getByRole("button", { name: `${resource.label} 다시 시도` });
      await retry.focus();
      await page.keyboard.press("Enter");
      await expect(alert).toHaveCount(0);
      await expect(page.getByText("검토 대상 기억", { exact: true })).toBeVisible();
      await expect(page.getByLabel("내용", { exact: true })).toHaveValue("retry keeps manuscript-related note");
      await expect(page.getByText("작품: 테스트 작품", { exact: true })).toBeVisible();
      await expect(page.getByLabel("근거 회차(선택)").locator("option")).toHaveCount(2);
    });
  }
}

test("M03 pending memory is distinct from successful empty lists", async ({ page }) => {
  await mockMemoryPage(page, "draft", false);
  let release!: () => void;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  await page.route("**/api/v1/projects/1/chapters", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/projects/1/memories", async (route) => { await gate; await route.fulfill({ json: [] }); });
  try {
    await page.goto("/projects/1/memory");
    await expect(page.getByText("기억을 불러오는 중…", { exact: true })).toBeVisible();
    await expect(page.getByText("조건에 맞는 장편 기억이 없습니다.", { exact: true })).toHaveCount(0);
    await page.getByLabel("내용", { exact: true }).fill("loading keeps input");
    release();
    await expect(page.getByText("조건에 맞는 장편 기억이 없습니다.", { exact: true })).toBeVisible();
    await expect(page.getByText("기억을 불러오는 중…", { exact: true })).toHaveCount(0);
    await expect(page.getByRole("alert")).toHaveCount(0);
    await expect(page.getByLabel("근거 회차(선택)").locator("option")).toHaveCount(1);
    await expect(page.getByLabel("내용", { exact: true })).toHaveValue("loading keeps input");
  } finally { release(); }
});

for (const action of ["승인", "폐기"]) {
  for (const complete of [false, true]) {
    for (const filtered of [false, true]) {
      test(`M04 keyboard ${action} ${complete ? "complete" : "cancel"} ${filtered ? "filtered" : "all"} restores stable focus`, async ({ page }) => {
        await mockMemoryPage(page);
        if (filtered) await page.getByLabel("기억 상태 필터").selectOption("draft");
        const trigger = page.getByRole("button", { name: action, exact: true });
        await trigger.focus();
        await page.keyboard.press("Enter");
        await expect(page.getByRole("button", { name: "확인", exact: true })).toBeFocused();
        if (!complete) await page.getByRole("button", { name: "취소", exact: true }).focus();
        await page.keyboard.press("Enter");
        await expect(page.getByRole("group", { name: "장편 기억 상태 변경 확인" })).toHaveCount(0);
        if (complete) {
          await expect(page.getByRole("region", { name: "장편 기억 목록" })).toBeFocused();
          if (filtered) await expect(page.locator("article")).toHaveCount(0);
          else await expect(page.locator("article")).toHaveCount(1);
        } else await expect(trigger).toBeFocused();
        const scan = await new AxeBuilder({ page }).analyze();
        expect(scan.violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toHaveLength(0);
      });
    }
  }
}

test("M04 completion waits for held list refetch before resolving removed trigger focus", async ({ page }) => {
  await mockMemoryPage(page);
  let release!: () => void;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  let held = false;
  await page.route("**/api/v1/projects/1/memories", async (route) => {
    held = true;
    await gate;
    return route.fulfill({ json: [] });
  });
  try {
    await page.getByRole("button", { name: "승인", exact: true }).focus();
    await page.keyboard.press("Enter");
    await page.keyboard.press("Enter");
    await expect.poll(() => held).toBe(true);
    release();
    await expect(page.locator("article")).toHaveCount(0);
    await expect(page.getByRole("region", { name: "장편 기억 목록" })).toBeFocused();
  } finally { release(); }
});

test("M01 current-screen PATCH failure retains confirmation and input and permits retry", async ({ page }) => {
  await mockMemoryPage(page);
  let failing = true;
  await page.route("**/api/v1/projects/1/memories/1", (route) => failing
    ? route.fulfill({ status: 500, json: { detail: "current screen patch failure" } })
    : route.fallback());
  await page.getByLabel("내용", { exact: true }).fill("current-screen pending note");
  await page.getByRole("button", { name: "승인", exact: true }).click();
  await page.getByRole("button", { name: "확인", exact: true }).click();
  await expect(page.getByText("기억 상태 변경 실패: current screen patch failure", { exact: true })).toBeVisible();
  await expect(page.getByText("이 기억을 승인할까요? 조건에 맞으면 AI 집필에 참고됩니다.", { exact: true })).toBeVisible();
  await expect(page.getByLabel("내용", { exact: true })).toHaveValue("current-screen pending note");
  await expect(page.getByRole("button", { name: "확인", exact: true })).toBeEnabled();
  failing = false;
  await page.getByRole("button", { name: "확인", exact: true }).click();
  await expect(page.getByRole("group", { name: "장편 기억 상태 변경 확인" })).toHaveCount(0);
  await expect(page.getByText("장편 기억 상태를 변경했습니다.", { exact: true })).toBeVisible();
  await expect(page.getByLabel("내용", { exact: true })).toHaveValue("current-screen pending note");
});
