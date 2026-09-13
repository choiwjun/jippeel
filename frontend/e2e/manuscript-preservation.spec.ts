import { expect, type Page } from "@playwright/test";
import { test, registerManuscriptApi, type ManuscriptFixtureRoute } from "./manuscript-http-fixture";

type Chapter = {
  id: number;
  project_id: number;
  volume: number | null;
  sort_order: number;
  title: string;
  status: "초고" | "수정중" | "완료";
  word_count_cache: number;
  memo: string | null;
  created_at: string;
  updated_at: string;
  revision: number;
  content_md: string;
};

type Snapshot = {
  id: number;
  chapter_id: number;
  revision: number;
  content_md: string;
  reason: string;
  created_at: string;
};

function now() {
  return new Date("2026-09-07T00:00:00.000Z").toISOString();
}

function makeChapter(
  id: number,
  project_id: number,
  title: string,
  content_md = "",
  revision = 0,
): Chapter {
  return {
    id,
    project_id,
    volume: 1,
    sort_order: id,
    title,
    status: "초고",
    word_count_cache: content_md.replace(/\s/g, "").length,
    memo: null,
    created_at: now(),
    updated_at: now(),
    revision,
    content_md,
  };
}

class HeldRoute {
  route: ManuscriptFixtureRoute;
  body: any;
  constructor(route: ManuscriptFixtureRoute) {
    this.route = route;
    this.body = JSON.parse(route.request().postData() ?? "{}");
  }
  async fulfill(detail: Chapter) {
    await this.route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(detail),
    });
  }
}

async function setupFixture(page: Page) {
  const chapters = new Map<number, Chapter>([
    [10, makeChapter(10, 1, "1화", "", 0)],
    [11, makeChapter(11, 1, "2화", "second chapter", 0)],
    [20, makeChapter(20, 2, "다른 작품 1화", "other project chapter", 0)],
  ]);
  const snapshots = new Map<number, Snapshot[]>([
    [
      10,
      [
        {
          id: 501,
          chapter_id: 10,
          revision: 0,
          content_md: "snapshot text",
          reason: "autosave",
          created_at: now(),
        },
      ],
    ],
  ]);
  const writes: Array<{ chapterId: number; body: any }> = [];
  const heldWrites: HeldRoute[] = [];
  const heldAccepts: HeldRoute[] = [];
  const heldMerges: HeldRoute[] = [];
  const heldRestores: HeldRoute[] = [];
  const heldChapterGets: HeldRoute[] = [];
  let abortNextChapterGet = false;
  let holdNextChapterGet = false;
  let abortNextSaveBeforeMutation = false;
  let abortNextSaveAfterMutation = false;
  let holdNextAccept = false;
  let holdNextMerge = false;
  let holdNextRestore = false;
  const refinedRuns = new Map<
    number,
    { id: number; chapter_id: number; base_revision: number }
  >();
  let nextRunId = 900;

  await registerManuscriptApi(page, async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace("/api/v1", "");
    const method = route.request().method();
    const json = (status: number, body: unknown) =>
      route.fulfill({
        status,
        contentType: "application/json",
        body: JSON.stringify(body),
      });
    const noContent = () => route.fulfill({ status: 204, body: "" });
    const requestBody = () => JSON.parse(route.request().postData() ?? "{}");

    if (method === "GET" && path === "/projects") {
      return json(200, [
        {
          id: 1,
          title: "원고 보존",
          genre: null,
          synopsis: null,
          platform_note: null,
          created_at: now(),
          updated_at: now(),
          chapter_count: 2,
          total_chars: 0,
        },
        {
          id: 2,
          title: "다른 작품",
          genre: null,
          synopsis: null,
          platform_note: null,
          created_at: now(),
          updated_at: now(),
          chapter_count: 1,
          total_chars: 0,
        },
      ]);
    }
    const chapterListMatch = path.match(/^\/projects\/(\d+)\/chapters$/);
    if (method === "GET" && chapterListMatch) {
      const pid = Number(chapterListMatch[1]);
      return json(
        200,
        [...chapters.values()]
          .filter((c) => c.project_id === pid)
          .map(({ content_md: _contentMd, ...meta }) => meta),
      );
    }
    if (method === "POST" && chapterListMatch) {
      const pid = Number(chapterListMatch[1]);
      const id = pid === 1 ? 12 : 21;
      const c = makeChapter(id, pid, requestBody().title ?? "", "", 0);
      chapters.set(id, c);
      return json(200, { ...c, content_md: undefined });
    }
    const chapterMatch = path.match(/^\/chapters\/(\d+)$/);
    if (method === "GET" && chapterMatch) {
      if (abortNextChapterGet) {
        abortNextChapterGet = false;
        return json(503, { detail: "서버 원고를 새로고침하지 못했습니다." });
      }
      if (holdNextChapterGet) {
        holdNextChapterGet = false;
        heldChapterGets.push(new HeldRoute(route));
        return;
      }
      const c = chapters.get(Number(chapterMatch[1]));
      return c ? json(200, c) : json(404, { detail: "not found" });
    }
    if (method === "PATCH" && chapterMatch) {
      const id = Number(chapterMatch[1]);
      const c = chapters.get(id)!;
      const next = { ...c, ...requestBody(), updated_at: now() };
      chapters.set(id, next);
      return json(200, next);
    }
    const contentMatch = path.match(/^\/chapters\/(\d+)\/content$/);
    if (method === "PUT" && contentMatch) {
      const chapterId = Number(contentMatch[1]);
      const body = requestBody();
      writes.push({ chapterId, body });
      if (abortNextSaveBeforeMutation) {
        abortNextSaveBeforeMutation = false;
        return route.abort("failed");
      }
      if (
        body.hold === true ||
        (chapterId === 10 &&
          heldWrites.length === 0 &&
          body.content_md === "first draft")
      ) {
        heldWrites.push(new HeldRoute(route));
        return;
      }
      const current = chapters.get(chapterId)!;
      if (body.expected_revision !== current.revision) {
        return json(409, {
          detail: {
            code: "revision_conflict",
            message: "서버에 더 최신 원고가 있습니다.",
            current_revision: current.revision,
          },
        });
      }
      const next = {
        ...current,
        content_md: body.content_md,
        revision:
          current.content_md === body.content_md
            ? current.revision
            : current.revision + 1,
        updated_at: now(),
        word_count_cache: String(body.content_md).replace(/\s/g, "").length,
      };
      chapters.set(chapterId, next);
      if (abortNextSaveAfterMutation) {
        abortNextSaveAfterMutation = false;
        return route.abort("failed");
      }
      return json(200, next);
    }
    if (method === "GET" && path === "/ai/presets") return json(200, []);
    if (method === "GET" && path.match(/^\/projects\/\d+\/foreshadows\/match$/))
      return json(200, []);
    if (method === "POST" && path === "/refine") {
      const body = requestBody();
      const current = chapters.get(Number(body.chapter_id))!;
      if (body.expected_revision !== current.revision)
        return json(409, {
          detail: {
            code: "revision_conflict",
            message: "윤문 전 원고가 최신이 아닙니다.",
            current_revision: current.revision,
          },
        });
      const runId = nextRunId++;
      refinedRuns.set(runId, {
        id: runId,
        chapter_id: current.id,
        base_revision: current.revision,
      });
      return json(200, {
        run_id: runId,
        base_revision: current.revision,
        route_hint: "light",
        spans: [],
        original: current.content_md,
        refined: `${current.content_md}\nrefined`,
        changed_ratio: 0.1,
        gate: "pass",
        status: "ok",
      });
    }
    const acceptMatch = path.match(/^\/refine\/runs\/(\d+)\/accept$/);
    if (method === "POST" && acceptMatch) {
      const run = refinedRuns.get(Number(acceptMatch[1]))!;
      const current = chapters.get(run.chapter_id)!;
      if (current.revision !== run.base_revision)
        return json(409, {
          detail: {
            code: "revision_conflict",
            message: "윤문 실행 뒤 원고가 바뀌었습니다.",
            current_revision: current.revision,
          },
        });
      const next = {
        ...current,
        content_md: `${current.content_md}\nrefined`,
        revision: current.revision + 1,
        updated_at: now(),
      };
      if (holdNextAccept) {
        holdNextAccept = false;
        heldAccepts.push(new HeldRoute(route));
        return;
      }
      chapters.set(current.id, next);
      return json(200, next);
    }
    const rejectMatch = path.match(/^\/refine\/runs\/(\d+)\/reject$/);
    if (method === "POST" && rejectMatch) return noContent();
    const scenesMatch = path.match(/^\/chapters\/(\d+)\/scenes$/);
    if (method === "GET" && scenesMatch)
      return json(200, [
        {
          id: 701,
          chapter_id: Number(scenesMatch[1]),
          sort_order: 1,
          title: "장면 A",
          content_md: "scene text",
        },
      ]);
    if (method === "POST" && scenesMatch)
      return json(200, {
        id: 702,
        chapter_id: Number(scenesMatch[1]),
        sort_order: 2,
        title: requestBody().title,
        content_md: requestBody().content_md,
      });
    const sceneMatch = path.match(/^\/scenes\/(\d+)$/);
    if ((method === "PATCH" || method === "DELETE") && sceneMatch)
      return method === "DELETE"
        ? noContent()
        : json(200, {
            id: Number(sceneMatch[1]),
            chapter_id: 10,
            sort_order: 1,
            title: requestBody().title,
            content_md: requestBody().content_md,
          });
    const mergeMatch = path.match(/^\/chapters\/(\d+)\/content_from_scenes$/);
    if (method === "PUT" && mergeMatch) {
      const id = Number(mergeMatch[1]);
      const body = requestBody();
      const current = chapters.get(id)!;
      writes.push({ chapterId: id, body: { merge: true, ...body } });
      if (body.expected_revision !== current.revision)
        return json(409, {
          detail: {
            code: "revision_conflict",
            message: "장면 조립 전 원고가 최신이 아닙니다.",
            current_revision: current.revision,
          },
        });
      const next = {
        ...current,
        content_md: "scene text",
        revision: current.revision + 1,
        updated_at: now(),
      };
      if (holdNextMerge) {
        holdNextMerge = false;
        heldMerges.push(new HeldRoute(route));
        return;
      }
      chapters.set(id, next);
      return json(200, next);
    }
    const snapshotsMatch = path.match(/^\/chapters\/(\d+)\/snapshots$/);
    if (method === "GET" && snapshotsMatch) {
      return json(
        200,
        (snapshots.get(Number(snapshotsMatch[1])) ?? []).map(
          ({ content_md: _contentMd, ...meta }) => meta,
        ),
      );
    }
    const snapshotDetailMatch = path.match(
      /^\/chapters\/(\d+)\/snapshots\/(\d+)$/,
    );
    if (method === "GET" && snapshotDetailMatch) {
      const snap = (snapshots.get(Number(snapshotDetailMatch[1])) ?? []).find(
        (s) => s.id === Number(snapshotDetailMatch[2]),
      );
      return snap ? json(200, snap) : json(404, { detail: "not found" });
    }
    const restoreMatch = path.match(/^\/chapters\/(\d+)\/restore$/);
    if (method === "POST" && restoreMatch) {
      const id = Number(restoreMatch[1]);
      const body = requestBody();
      const current = chapters.get(id)!;
      writes.push({ chapterId: id, body: { restore: true, ...body } });
      if (body.expected_revision !== current.revision)
        return json(409, {
          detail: {
            code: "revision_conflict",
            message: "복구 전 원고가 최신이 아닙니다.",
            current_revision: current.revision,
          },
        });
      const snap = (snapshots.get(id) ?? []).find(
        (s) => s.id === body.snapshot_id,
      )!;
      const next = {
        ...current,
        content_md: snap.content_md,
        revision: current.revision + 1,
        updated_at: now(),
      };
      if (holdNextRestore) {
        holdNextRestore = false;
        heldRestores.push(new HeldRoute(route));
        return;
      }
      chapters.set(id, next);
      return json(200, next);
    }
    throw new Error(
      `Unexpected production API request in preservation fixture: ${method} ${path}`,
    );
  });

  return {
    chapters,
    writes,
    heldWrites,
    heldAccepts,
    heldMerges,
    heldRestores,
    heldChapterGets,
    abortNextChapterGet: () => {
      abortNextChapterGet = true;
    },
    holdNextChapterGet: () => {
      holdNextChapterGet = true;
    },
    holdNextAccept: () => {
      holdNextAccept = true;
    },
    holdNextMerge: () => {
      holdNextMerge = true;
    },
    holdNextRestore: () => {
      holdNextRestore = true;
    },
    abortNextSaveBeforeMutation: () => {
      abortNextSaveBeforeMutation = true;
    },
    abortNextSaveAfterMutation: () => {
      abortNextSaveAfterMutation = true;
    },
  };
}

async function openEditor(page: Page, projectId = 1) {
  await page.goto(`/projects/${projectId}/write`);
  await expect(page.locator(".cm-content")).toBeVisible();
}

async function fillEditor(page: Page, text: string) {
  const editor = page.locator(".cm-content");
  await editor.click();
  await editor.fill(text);
}

async function storedDraft(page: Page, projectId = 1, chapterId = 10) {
  return page.evaluate(
    ([pid, cid]) => {
      const raw = localStorage.getItem(
        `jippeel:manuscript-draft:v1:${pid}:${cid}`,
      );
      return raw
        ? (JSON.parse(raw) as {
            text: string;
            baseRevision: number;
            editSequence: number;
          })
        : null;
    },
    [projectId, chapterId],
  );
}

test.describe
  .serial("manuscript preservation frontend fixture", () => {
    test("serializes delayed per-chapter saves and preserves newer typing", async ({
      page,
    }) => {
      const f = await setupFixture(page);
      await openEditor(page, 1);

      await fillEditor(page, "first draft");
      await expect.poll(() => f.heldWrites.length, { timeout: 5_000 }).toBe(1);
      const firstWrite = f.heldWrites[0].body;
      expect(firstWrite.expected_revision).toBe(0);
      expect(firstWrite.content_md).toBe("first draft");

      await fillEditor(page, "latest draft");
      f.chapters.set(10, {
        ...f.chapters.get(10)!,
        content_md: "first draft",
        revision: 1,
      });
      await f.heldWrites[0].fulfill(f.chapters.get(10)!);

      await expect
        .poll(() => f.writes.filter((w) => w.chapterId === 10).length, {
          timeout: 8_000,
        })
        .toBe(2);
      const secondWrite = f.writes.filter((w) => w.chapterId === 10)[1].body;
      expect(secondWrite.expected_revision).toBe(1);
      expect(secondWrite.content_md).toBe("latest draft");

      await page.getByRole("tab", { name: "미리보기" }).click();
      await expect(page.getByText("latest draft")).toBeVisible();
      await page.getByRole("tab", { name: "편집" }).click();
      await expect(page.locator(".cm-content")).toContainText("latest draft");
    });

    test("project switch rejects stale selected chapters and never writes under the new project context", async ({
      page,
    }) => {
      const f = await setupFixture(page);
      await openEditor(page, 1);
      await expect(page.locator(".cm-content")).toContainText("");
      await fillEditor(page, "project one unsaved");

      await page.goto("/projects/2/write");
      await expect(page.locator(".cm-content")).toContainText(
        "other project chapter",
      );
      await expect
        .poll(() =>
          f.writes.some(
            (w) =>
              w.chapterId === 20 && w.body.content_md === "project one unsaved",
          ),
        )
        .toBe(false);
    });

    test("unresolved mismatched recovery locks editing, survives reload, and local choice remains recoverable while saving", async ({
      page,
    }) => {
      const f = await setupFixture(page);
      f.chapters.set(10, {
        ...f.chapters.get(10)!,
        content_md: "server newer recovery",
        revision: 2,
      });
      await page.addInitScript(() =>
        localStorage.setItem(
          "jippeel:manuscript-draft:v1:1:10",
          JSON.stringify({
            projectId: 1,
            chapterId: 10,
            version: 1,
            baseRevision: 0,
            editSequence: 5,
            text: "first draft",
            updatedAt: Date.now(),
          }),
        ),
      );
      await page.goto("/projects/1/write");

      await expect(
        page.getByText(
          "로컬 복구본과 서버 원고가 다릅니다. 자동으로 덮어쓰지 않습니다.",
        ),
      ).toBeVisible();
      await expect(
        page.getByText("복구 선택 전에는 편집이 잠겨 있습니다."),
      ).toBeVisible();
      await expect(page.locator(".cm-content")).toHaveCount(0);

      await page.keyboard.type("ignored typing while unresolved");
      await expect(await storedDraft(page)).toMatchObject({
        text: "first draft",
        baseRevision: 0,
      });

      await page.reload();
      await expect(
        page.getByText(
          "로컬 복구본과 서버 원고가 다릅니다. 자동으로 덮어쓰지 않습니다.",
        ),
      ).toBeVisible();
      await expect(await storedDraft(page)).toMatchObject({
        text: "first draft",
        baseRevision: 0,
      });

      await page.getByRole("button", { name: "로컬 복구본 불러오기" }).click();
      await expect(page.locator(".cm-content")).toContainText("first draft");
      await expect.poll(() => f.heldWrites.length, { timeout: 5_000 }).toBe(1);
      expect(f.heldWrites[0].body).toMatchObject({
        content_md: "first draft",
        expected_revision: 2,
      });
      await expect(await storedDraft(page)).toMatchObject({
        text: "first draft",
        baseRevision: 2,
      });
    });

    test("server choice refreshes to latest paired server body and never PUTs stale displayed text", async ({
      page,
    }) => {
      const f = await setupFixture(page);
      f.chapters.set(10, {
        ...f.chapters.get(10)!,
        content_md: "server body v1",
        revision: 2,
      });
      await page.addInitScript(() =>
        localStorage.setItem(
          "jippeel:manuscript-draft:v1:1:10",
          JSON.stringify({
            projectId: 1,
            chapterId: 10,
            version: 1,
            baseRevision: 0,
            editSequence: 4,
            text: "local old recovery",
            updatedAt: Date.now(),
          }),
        ),
      );
      await page.goto("/projects/1/write");
      await expect(
        page.getByRole("alert").getByText("server body v1").first(),
      ).toBeVisible();

      f.chapters.set(10, {
        ...f.chapters.get(10)!,
        content_md: "server body v2",
        revision: 3,
      });
      await page.getByRole("button", { name: "서버 원고 새로고침" }).click();
      await expect(page.getByText("서버 원고 (revision 3)")).toBeVisible();
      await expect(
        page.getByRole("alert").getByText("server body v2").first(),
      ).toBeVisible();

      await page.getByRole("button", { name: "서버 원고로 계속" }).click();
      await expect(page.locator(".cm-content")).toContainText("server body v2");
      expect(
        f.writes.some(
          (w) =>
            w.body.content_md === "server body v1" ||
            w.body.content_md === "server body v2",
        ),
      ).toBe(false);
      expect(await storedDraft(page)).toBeNull();
    });

    test("failed server recovery choice keeps original draft locked until successful retry", async ({
      page,
    }) => {
      const f = await setupFixture(page);
      f.chapters.set(10, {
        ...f.chapters.get(10)!,
        content_md: "server stale before retry",
        revision: 2,
      });
      await page.addInitScript(() =>
        localStorage.setItem(
          "jippeel:manuscript-draft:v1:1:10",
          JSON.stringify({
            projectId: 1,
            chapterId: 10,
            version: 1,
            baseRevision: 0,
            editSequence: 7,
            text: "local retry recovery",
            updatedAt: 12345,
          }),
        ),
      );
      await page.goto("/projects/1/write");
      await expect(
        page.getByText("복구 선택 전에는 편집이 잠겨 있습니다."),
      ).toBeVisible();

      f.abortNextChapterGet();
      await page.getByRole("button", { name: "서버 원고로 계속" }).click();
      await expect(
        page.getByText("서버 원고를 새로고침하지 못했습니다."),
      ).toBeVisible();
      await expect(
        page.getByText("복구 선택 전에는 편집이 잠겨 있습니다."),
      ).toBeVisible();
      await expect(
        page.getByRole("alert").getByText("local retry recovery").first(),
      ).toBeVisible();
      await expect(
        page.getByRole("alert").getByText("server stale before retry").first(),
      ).toBeVisible();
      await expect(page.locator(".cm-content")).toHaveCount(0);
      expect(await storedDraft(page)).toEqual({
        projectId: 1,
        chapterId: 10,
        version: 1,
        text: "local retry recovery",
        baseRevision: 0,
        editSequence: 7,
        updatedAt: 12345,
      });
      expect(f.writes).toHaveLength(0);

      f.chapters.set(10, {
        ...f.chapters.get(10)!,
        content_md: "server latest after retry",
        revision: 3,
      });
      await page.getByRole("button", { name: "서버 원고로 계속" }).click();
      await expect(page.locator(".cm-content")).toContainText(
        "server latest after retry",
      );
      expect(f.writes).toHaveLength(0);
      expect(await storedDraft(page)).toBeNull();
    });

    test("server recovery choice disables competing actions while latest server body is pending", async ({
      page,
    }) => {
      const f = await setupFixture(page);
      f.chapters.set(10, {
        ...f.chapters.get(10)!,
        content_md: "server body before pending",
        revision: 2,
      });
      await page.addInitScript(() =>
        localStorage.setItem(
          "jippeel:manuscript-draft:v1:1:10",
          JSON.stringify({
            projectId: 1,
            chapterId: 10,
            version: 1,
            baseRevision: 0,
            editSequence: 8,
            text: "local pending recovery",
            updatedAt: 12345,
          }),
        ),
      );
      await page.goto("/projects/1/write");
      await expect(
        page.getByRole("button", { name: "서버 원고로 계속" }),
      ).toBeVisible();

      f.chapters.set(10, {
        ...f.chapters.get(10)!,
        content_md: "server body after pending",
        revision: 3,
      });
      f.holdNextChapterGet();
      await page
        .getByRole("button", { name: "서버 원고로 계속" })
        .evaluate((button) => (button as HTMLButtonElement).click());
      await expect(
        page.getByRole("button", { name: "로컬 복구본 불러오기" }),
      ).toBeDisabled();
      await expect(
        page.getByRole("button", { name: "서버 원고 새로고침" }),
      ).toBeDisabled();
      await expect(
        page.getByRole("button", { name: "서버 원고로 계속" }),
      ).toBeDisabled();
      await expect(page.getByText("서버 원고 확인 중…")).toBeVisible();
      await expect
        .poll(() => f.heldChapterGets.length, { timeout: 5_000 })
        .toBe(1);
      expect(await storedDraft(page)).toEqual({
        projectId: 1,
        chapterId: 10,
        version: 1,
        text: "local pending recovery",
        baseRevision: 0,
        editSequence: 8,
        updatedAt: 12345,
      });

      await f.heldChapterGets[0].fulfill(f.chapters.get(10)!);
      await expect(page.locator(".cm-content")).toContainText(
        "server body after pending",
      );
      expect(f.writes).toHaveLength(0);
      expect(await storedDraft(page)).toBeNull();
    });

    test("keeps ApiError detail for 409 and shows local/server conflict recovery", async ({
      page,
    }) => {
      const f = await setupFixture(page);
      f.chapters.set(10, {
        ...f.chapters.get(10)!,
        content_md: "server newer",
        revision: 2,
      });
      await openEditor(page, 1);
      // Rebase UI to old local base on purpose.
      await page.evaluate(() =>
        localStorage.setItem(
          "jippeel:manuscript-draft:v1:1:10",
          JSON.stringify({
            projectId: 1,
            chapterId: 10,
            version: 1,
            baseRevision: 0,
            editSequence: 1,
            text: "local draft",
          }),
        ),
      );
      await page.reload();
      await expect(
        page.getByText(
          "로컬 복구본과 서버 원고가 다릅니다. 자동으로 덮어쓰지 않습니다.",
        ),
      ).toBeVisible();
      await expect(
        page.getByRole("alert").getByText("local draft").first(),
      ).toBeVisible();
      await expect(
        page.getByRole("alert").getByText("server newer").first(),
      ).toBeVisible();

      await page.getByRole("button", { name: "로컬 복구본 불러오기" }).click();
      f.chapters.set(10, {
        ...f.chapters.get(10)!,
        content_md: "even newer server",
        revision: 3,
      });
      await page.locator(".cm-content").click();
      await page.keyboard.press(
        process.platform === "darwin" ? "Meta+S" : "Control+S",
      );
      await expect(page.getByText("저장 충돌 — 원고 확인 필요")).toBeVisible();
      await expect(page.getByText(/current_revision 3/)).toBeVisible();
      await expect(page.locator(".cm-content")).toContainText("local draft");
    });

    test("recovers reload drafts, survives storage failure, and preserves text after network error", async ({
      page,
    }) => {
      await setupFixture(page);
      await openEditor(page, 1);
      await fillEditor(page, "reload local draft");
      await page.reload();
      await expect(page.locator(".cm-content")).toContainText(
        "reload local draft",
      );

      await page.addInitScript(() => {
        const original = Storage.prototype.setItem;
        Storage.prototype.setItem = function (key: string, value: string) {
          if (key.startsWith("jippeel:manuscript-draft:v1:"))
            throw new Error("quota exceeded");
          return original.call(this, key, value);
        };
      });
      await page.reload();
      await fillEditor(page, "storage still editable");
      await expect(page.getByText(/복구본 저장에 실패/)).toBeVisible();
      await expect(page.locator(".cm-content")).toContainText(
        "storage still editable",
      );
    });

    test("preserves local text on network failure and reconciles lost save acknowledgements", async ({
      page,
    }) => {
      const f = await setupFixture(page);
      await openEditor(page, 1);

      f.abortNextSaveBeforeMutation();
      await fillEditor(page, "network local draft");
      await page.locator(".cm-content").click();
      await page.keyboard.press(
        process.platform === "darwin" ? "Meta+S" : "Control+S",
      );
      await expect(page.getByText("저장 실패 — 원고 보존됨")).toBeVisible();
      await expect(page.locator(".cm-content")).toContainText(
        "network local draft",
      );

      f.abortNextSaveAfterMutation();
      await fillEditor(page, "lost ack draft");
      await page.locator(".cm-content").click();
      await page.keyboard.press(
        process.platform === "darwin" ? "Meta+S" : "Control+S",
      );
      await expect
        .poll(() => f.chapters.get(10)?.content_md, { timeout: 8_000 })
        .toBe("lost ack draft");
      await expect(page.locator(".cm-content")).toContainText("lost ack draft");
      await expect(page.getByText(/저장됨 ·/)).toBeVisible();
    });

    test("does not let a pending refine accept response overwrite a late local edit", async ({
      page,
    }) => {
      const f = await setupFixture(page);
      await openEditor(page, 1);
      await fillEditor(page, "before refine");
      await page.getByRole("button", { name: "윤문 리포트" }).click();
      await page.getByRole("button", { name: "🔍 윤문 실행" }).click();
      await expect
        .poll(
          () =>
            f.writes.some(
              (w) =>
                w.chapterId === 10 && w.body.content_md === "before refine",
            ),
          { timeout: 8_000 },
        )
        .toBe(true);
      await expect(page.getByRole("button", { name: "수락" })).toBeVisible();

      f.holdNextAccept();
      await page.getByRole("button", { name: "수락" }).click();
      await expect.poll(() => f.heldAccepts.length, { timeout: 5_000 }).toBe(1);
      await page.getByRole("button", { name: "패널 닫기" }).click();
      await fillEditor(page, "late local edit");
      await expect(await storedDraft(page)).toMatchObject({
        text: "late local edit",
      });

      const accepted = {
        ...f.chapters.get(10)!,
        content_md: "before refine\nrefined",
        revision: 2,
        updated_at: now(),
      };
      f.chapters.set(10, accepted);
      await f.heldAccepts[0].fulfill(accepted);

      await expect(page.locator(".cm-content")).toContainText(
        "late local edit",
      );
      await expect(await storedDraft(page)).toMatchObject({
        text: "late local edit",
      });
      await expect(page.getByText("저장 충돌 — 원고 확인 필요")).toBeVisible();
    });

    test("does not let a pending scene merge response overwrite a late edit or transfer to another chapter", async ({
      page,
    }) => {
      test.setTimeout(20_000);
      const f = await setupFixture(page);
      await openEditor(page, 1);
      await fillEditor(page, "before scene merge");
      await page.getByRole("button", { name: "AI 패널" }).click();
      await page.getByRole("button", { name: /장면 관리/ }).click();
      f.holdNextMerge();
      page.once("dialog", (d) => d.accept());
      await page.evaluate(() => {
        window.confirm = () => true;
      });
      await page
        .getByRole("button", { name: /본문으로 합치기/ })
        .click({ timeout: 5_000 });
      await expect.poll(() => f.heldMerges.length, { timeout: 5_000 }).toBe(1);
      await page.keyboard.press("Escape");
      const closePanel = page.getByRole("button", { name: "패널 닫기" });
      if (await closePanel.isVisible()) await closePanel.click();
      await fillEditor(page, "late scene edit");
      await expect(await storedDraft(page)).toMatchObject({
        text: "late scene edit",
      });

      await page.locator("aside button").filter({ hasText: /^2화/ }).click();
      await expect(page.locator(".cm-content")).toContainText("second chapter");
      const merged = {
        ...f.chapters.get(10)!,
        content_md: "scene text",
        revision: 2,
        updated_at: now(),
      };
      f.chapters.set(10, merged);
      await f.heldMerges[0].fulfill(merged);

      await expect(page.locator(".cm-content")).toContainText("second chapter");
      await page.locator("aside button").filter({ hasText: /^1화/ }).click();
      await expect(page.locator(".cm-content")).toContainText(
        "late scene edit",
      );
      await expect(await storedDraft(page)).toMatchObject({
        text: "late scene edit",
      });
    });

    test("does not let a pending snapshot restore response overwrite a late local edit", async ({
      page,
    }) => {
      const f = await setupFixture(page);
      await openEditor(page, 1);
      await fillEditor(page, "before restore late");
      await page.getByRole("button", { name: /복구본/ }).click();
      await page.getByRole("button", { name: /revision 0/ }).click();
      await expect(page.getByText("snapshot text")).toBeVisible();
      f.holdNextRestore();
      await page.getByRole("button", { name: /이 복구본으로 복원/ }).click();
      await expect
        .poll(() => f.heldRestores.length, { timeout: 5_000 })
        .toBe(1);
      await page.keyboard.press("Escape");
      await fillEditor(page, "late restore edit");
      await expect(await storedDraft(page)).toMatchObject({
        text: "late restore edit",
      });

      const restored = {
        ...f.chapters.get(10)!,
        content_md: "snapshot text",
        revision: 2,
        updated_at: now(),
      };
      f.chapters.set(10, restored);
      await f.heldRestores[0].fulfill(restored);

      await expect(page.locator(".cm-content")).toContainText(
        "late restore edit",
      );
      await expect(await storedDraft(page)).toMatchObject({
        text: "late restore edit",
      });
      await expect(page.getByText("저장 충돌 — 원고 확인 필요")).toBeVisible();
    });

    test("does not acknowledge lost save responses when GET returns different text", async ({
      page,
    }) => {
      const f = await setupFixture(page);
      await openEditor(page, 1);
      f.abortNextSaveBeforeMutation();
      await fillEditor(page, "lost negative draft");
      f.chapters.set(10, {
        ...f.chapters.get(10)!,
        content_md: "different server text",
        revision: 7,
      });
      await page.locator(".cm-content").click();
      await page.keyboard.press(
        process.platform === "darwin" ? "Meta+S" : "Control+S",
      );

      await expect(page.getByText("저장 실패 — 원고 보존됨")).toBeVisible();
      await expect(page.locator(".cm-content")).toContainText(
        "lost negative draft",
      );
      await expect(await storedDraft(page)).toMatchObject({
        text: "lost negative draft",
      });
    });

    test("pagehide uses revision contract and beforeunload leaves recoverable text", async ({
      page,
    }) => {
      const f = await setupFixture(page);
      await openEditor(page, 1);
      await fillEditor(page, "pagehide local draft");
      const beforeUnloadPrevented = await page.evaluate(() => {
        const event = new Event("beforeunload", { cancelable: true });
        return !window.dispatchEvent(event);
      });
      expect(beforeUnloadPrevented).toBe(true);
      await expect(await storedDraft(page)).toMatchObject({
        text: "pagehide local draft",
        baseRevision: 0,
      });

      await page.evaluate(() =>
        window.dispatchEvent(new PageTransitionEvent("pagehide")),
      );
      await expect
        .poll(
          () =>
            f.writes.some(
              (w) =>
                w.chapterId === 10 &&
                w.body.content_md === "pagehide local draft",
            ),
          { timeout: 5_000 },
        )
        .toBe(true);
      const pagehideWrite = f.writes.find(
        (w) =>
          w.chapterId === 10 && w.body.content_md === "pagehide local draft",
      )!;
      expect(pagehideWrite.body.expected_revision).toBe(0);
      await expect(await storedDraft(page)).toMatchObject({
        text: "pagehide local draft",
      });
    });

    test("flushes before refine start, sends expected_revision, and blocks stale accept safely", async ({
      page,
    }) => {
      const f = await setupFixture(page);
      await openEditor(page, 1);
      await fillEditor(page, "before refine");
      await page.getByRole("button", { name: "윤문 리포트" }).click();
      await page
        .locator('select[aria-label="윤문 강도"]')
        .selectOption("light");
      const refineRequestPromise = page.waitForRequest(
        (request) =>
          request.method() === "POST" &&
          new URL(request.url()).pathname === "/api/v1/refine",
      );
      await page.getByRole("button", { name: "🔍 윤문 실행" }).click();

      await expect
        .poll(
          () =>
            f.writes.some(
              (w) =>
                w.chapterId === 10 && w.body.content_md === "before refine",
            ),
          { timeout: 8_000 },
        )
        .toBe(true);
      const refineRequest = await refineRequestPromise;
      const body = JSON.parse(refineRequest.postData() ?? "{}");
      expect(body.expected_revision).toBe(1);
      expect(body.chapter_id).toBe(10);
      await expect(
        page.getByRole("heading", { name: /변경률 게이트/ }),
      ).toBeVisible();

      f.chapters.set(10, {
        ...f.chapters.get(10)!,
        content_md: "changed elsewhere",
        revision: 2,
      });
      await page.getByRole("button", { name: "수락" }).click();
      await expect(
        page.getByText(/윤문 실행 뒤 원고가 바뀌었습니다|최신/),
      ).toBeVisible();
      await expect(page.locator(".cm-content")).not.toContainText("refined");
    });

    test("scene trigger is accessible and merge flushes with expected_revision", async ({
      page,
    }) => {
      const f = await setupFixture(page);
      await openEditor(page, 1);
      await fillEditor(page, "before scene merge");
      await page.getByRole("button", { name: "AI 패널" }).click();
      await expect(
        page.getByRole("button", { name: /장면 관리/ }),
      ).toBeVisible();
      await page.getByRole("button", { name: /장면 관리/ }).click();
      page.once("dialog", (d) => d.accept());
      await page.evaluate(() => {
        window.confirm = () => true;
      });
      await page
        .getByRole("button", { name: /본문으로 합치기/ })
        .click({ timeout: 5_000 });
      await expect
        .poll(() => f.writes.some((w) => w.body.merge === true), {
          timeout: 8_000,
        })
        .toBe(true);
      const merge = f.writes.find((w) => w.body.merge === true)!;
      expect(merge.body.expected_revision).toBe(1);
    });

    test("shows snapshot text before explicit restore and restore uses current revision", async ({
      page,
    }) => {
      const f = await setupFixture(page);
      await openEditor(page, 1);
      await fillEditor(page, "before restore");
      await page.getByRole("button", { name: /복구본/ }).click();
      await page.getByRole("button", { name: /revision 0/ }).click();
      await expect(page.getByText("snapshot text")).toBeVisible();
      await page.getByRole("button", { name: /이 복구본으로 복원/ }).click();
      await expect
        .poll(() => f.writes.some((w) => w.body.restore === true), {
          timeout: 8_000,
        })
        .toBe(true);
      const restore = f.writes.find((w) => w.body.restore === true)!;
      expect(restore.body.expected_revision).toBe(1);
      await expect(page.locator(".cm-content")).toContainText("snapshot text");
    });
  });

async function memoryRevisionFixture(page: Page, f: Awaited<ReturnType<typeof setupFixture>>) {
  const reads: number[] = [];
  await page.route("**/api/v1/projects/*", (route) => route.fulfill({ json: { id: 1, title: "원고 보존" } }));
  await page.route("**/api/v1/projects/*/memories*", (route) => {
    const pid = Number(route.request().url().match(/projects\/(\d+)/)?.[1]);
    reads.push(pid);
    return route.fulfill({ json: [{
      id: pid, project_id: pid, chapter_id: pid === 1 ? 10 : 20, kind: "fact",
      body: `project ${pid} provenance`, visibility: "approved", source_revision: 0,
      source_sha256: "a".repeat(64), source_chapter_title: "1화", provenance: {},
      effective_from_sort_order: null, effective_to_sort_order: null,
      stale: pid === 1 && f.chapters.get(10)!.revision > 0,
    }] });
  });
  await page.goto("/projects/1/memory");
  await expect(page.getByText("project 1 provenance")).toBeVisible();
  await expect(page.getByText("stale — 자동 주입 제외", { exact: true })).toHaveCount(0);
  expect(reads).toEqual([1]);
  await page.getByRole("link", { name: "✍ 회차 집필" }).click();
  await expect(page.locator(".cm-content")).toBeVisible();
  return reads;
}

for (const viewingPid of [1, 2]) {
  test(`M02 held save after editor unmount refreshes origin only while viewing ${viewingPid}`, async ({ page }) => {
    const f = await setupFixture(page);
    const reads = await memoryRevisionFixture(page, f);
    await fillEditor(page, "first draft");
    await expect.poll(() => f.heldWrites.length).toBe(1);
    expect(f.heldWrites[0].body).toEqual({ content_md: "first draft", expected_revision: 0 });
    await page.getByRole("link", { name: "🧠 장편 기억" }).click();
    if (viewingPid === 2) await page.evaluate(() => {
      history.pushState({}, "", "/projects/2/memory");
      dispatchEvent(new PopStateEvent("popstate"));
    });
    await expect(page.getByText(`project ${viewingPid} provenance`)).toBeVisible();
    expect(reads.filter((pid) => pid === 1)).toHaveLength(1);
    const next = { ...f.chapters.get(10)!, content_md: "first draft", revision: 1 };
    f.chapters.set(10, next);
    await f.heldWrites[0].fulfill(next);
    if (viewingPid === 2) {
      await page.waitForTimeout(150);
      expect(reads.filter((pid) => pid === 2)).toHaveLength(1);
      await page.evaluate(() => {
        history.pushState({}, "", "/projects/1/memory");
        dispatchEvent(new PopStateEvent("popstate"));
      });
    }
    await expect(page.getByText("stale — 자동 주입 제외", { exact: true })).toBeVisible();
    expect(reads.filter((pid) => pid === 1)).toHaveLength(2);
    await page.getByRole("link", { name: "✍ 회차 집필" }).click();
    await expect(page.locator(".cm-content")).toHaveText("first draft");
    expect(f.writes).toEqual([{ chapterId: 10, body: { content_md: "first draft", expected_revision: 0 } }]);
  });
}

for (const succeeds of [true, false]) {
  test(`M02 live save ${succeeds ? "success" : "failure"} only refreshes memory on revision success`, async ({ page }) => {
    const f = await setupFixture(page);
    const reads = await memoryRevisionFixture(page, f);
    if (!succeeds) f.abortNextSaveBeforeMutation();
    await fillEditor(page, "live local manuscript");
    await page.keyboard.press("Control+s");
    if (succeeds) await expect.poll(() => f.chapters.get(10)!.revision).toBe(1);
    else await expect(page.getByText("저장 실패 — 원고 보존됨")).toBeVisible();
    await expect(page.locator(".cm-content")).toHaveText("live local manuscript");
    await page.getByRole("link", { name: "🧠 장편 기억" }).click();
    await expect(page.getByText("project 1 provenance")).toBeVisible();
    await expect(page.getByText("stale — 자동 주입 제외", { exact: true })).toHaveCount(succeeds ? 1 : 0);
    expect(reads).toHaveLength(succeeds ? 2 : 1);
    expect(f.writes[0]).toEqual({ chapterId: 10, body: { content_md: "live local manuscript", expected_revision: 0 } });
  });
}

for (const outcome of ["success", "late-edit", "failure"] as const) {
  test(`M02 restore ${outcome} preserves text and refreshes only successful revision`, async ({ page }) => {
    const f = await setupFixture(page);
    const reads = await memoryRevisionFixture(page, f);
    f.holdNextRestore();
    await page.getByRole("button", { name: "복구본", exact: true }).click();
    await page.getByRole("button", { name: /revision 0/ }).click();
    await expect(page.getByText("snapshot text", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "이 복구본으로 복원" }).click();
    await expect.poll(() => f.heldRestores.length).toBe(1);
    expect(f.heldRestores[0].body).toEqual({ snapshot_id: 501, expected_revision: 0 });
    if (outcome === "late-edit") {
      await page.getByRole("button", { name: "닫기", exact: true }).click();
      await fillEditor(page, "late local manuscript");
    }
    if (outcome === "failure") {
      await f.heldRestores[0].route.fulfill({ status: 500, json: { detail: "fixture restore failure" } });
      await expect(page.getByText("fixture restore failure", { exact: true })).toBeVisible();
      await page.getByRole("button", { name: "닫기", exact: true }).click();
    } else {
      const next = { ...f.chapters.get(10)!, content_md: "snapshot text", revision: 1 };
      f.chapters.set(10, next);
      await f.heldRestores[0].fulfill(next);
      await expect(page.locator(".cm-content")).toHaveText(outcome === "late-edit" ? "late local manuscript" : "snapshot text");
      if (outcome === "late-edit") await expect(page.getByText(/자동 덮어쓰기를 멈췄습니다/).first()).toBeVisible();
    }
    await page.getByRole("link", { name: "🧠 장편 기억" }).click();
    await expect(page.getByText("project 1 provenance")).toBeVisible();
    await expect(page.getByText("stale — 자동 주입 제외", { exact: true })).toHaveCount(outcome === "failure" ? 0 : 1);
    expect(reads).toHaveLength(outcome === "failure" ? 1 : 2);
    expect(f.chapters.get(10)!.revision).toBe(outcome === "failure" ? 0 : 1);
    await page.getByRole("link", { name: "✍ 회차 집필" }).click();
    await expect(page.locator(".cm-content")).toHaveText(outcome === "late-edit" ? "late local manuscript" : outcome === "success" ? "snapshot text" : "");
  });
}

test("fixture lifecycle routes pagehide keepalive through context on reload and page close", async ({ page }) => {
  const f = await setupFixture(page);
  await openEditor(page);
  await fillEditor(page, "reload keepalive manuscript");
  await page.reload();
  await expect.poll(() => f.writes.some((write) => write.body.content_md === "reload keepalive manuscript")).toBe(true);
  await expect(page.locator(".cm-content")).toHaveText("reload keepalive manuscript");
  await fillEditor(page, "closing keepalive manuscript");
  // Real document navigation fires pagehide while the BrowserContext fixture is alive.
  await page.goto("about:blank");
  await expect.poll(() => f.writes.some((write) => write.body.content_md === "closing keepalive manuscript")).toBe(true);
  expect(f.writes.map((write) => write.chapterId)).toEqual([10, 10]);
  expect(f.writes.map((write) => write.body.expected_revision)).toEqual([0, 1]);
  expect(f.chapters.get(10)!.content_md).toBe("closing keepalive manuscript");
  await page.close();
});

test("M02 cache notification exception cannot reclassify an acknowledged UI save", async ({ page }) => {
  const f = await setupFixture(page);
  const reads = await memoryRevisionFixture(page, f);
  const errors: string[] = [];
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  const ready = page.waitForEvent("console", { predicate: (message) => message.text() === "QUERY_CACHE_FAULT_READY" });
  const injected = page.evaluate(async (modulePath) => {
    const { queryClient } = await import(modulePath);
    let unsubscribe = () => {};
    let timeout: ReturnType<typeof setTimeout> | undefined;
    try {
      return await new Promise<{ count: number; queryKey: unknown[]; action: string }>((resolve, reject) => {
        let count = 0;
        unsubscribe = queryClient.getQueryCache().subscribe((event: {
          type: string; query?: { queryKey: unknown[] }; action?: { type: string };
        }) => {
          if (event.type !== "updated" || event.query?.queryKey[0] !== "memories" || event.query.queryKey[1] !== 1 || event.action?.type !== "invalidate") return;
          count += 1;
          resolve({ count, queryKey: event.query.queryKey, action: event.action.type });
          throw new Error("synthetic one-shot cache notification failure");
        });
        timeout = setTimeout(() => reject(new Error("Expected memory invalidation did not happen")), 30_000);
        console.debug("QUERY_CACHE_FAULT_READY");
      });
    } finally {
      unsubscribe();
      clearTimeout(timeout);
    }
  }, "/src/lib/queryClient.ts");
  await ready;
  await fillEditor(page, "acknowledged despite cache fault");
  await page.keyboard.press("Control+s");
  expect(await injected).toEqual({ count: 1, queryKey: ["memories", 1, "", "", "", ""], action: "invalidate" });
  await expect.poll(() => f.chapters.get(10)!.revision).toBe(1);
  await expect(page.locator(".cm-content")).toHaveText("acknowledged despite cache fault");
  await expect(page.getByText(/저장됨 ·/)).toBeVisible();
  expect(f.writes).toEqual([{ chapterId: 10, body: { content_md: "acknowledged despite cache fault", expected_revision: 0 } }]);
  expect(errors).toEqual(["Memory cache refresh failed after an acknowledged manuscript revision."]);
  // The finally cleanup already removed the subscriber; an ordinary second save stays healthy.
  await fillEditor(page, "normal save after subscriber cleanup");
  await page.keyboard.press("Control+s");
  await expect.poll(() => f.chapters.get(10)!.revision).toBe(2);
  await expect(page.getByText(/저장됨 ·/)).toBeVisible();
  expect(f.writes[1]).toEqual({ chapterId: 10, body: { content_md: "normal save after subscriber cleanup", expected_revision: 1 } });
  await page.getByRole("link", { name: "🧠 장편 기억" }).click();
  await expect(page.getByText("stale — 자동 주입 제외", { exact: true })).toBeVisible();
  expect(reads).toEqual([1, 1]);
  expect(errors).toEqual(["Memory cache refresh failed after an acknowledged manuscript revision."]);
});
