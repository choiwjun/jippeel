import { randomUUID } from "node:crypto";
import { appendFileSync, existsSync, mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import type { BrowserContext, Page, Request, Route } from "@playwright/test";
import { createServer } from "vite";
import { fixtureConfig } from "../vite.fixture.config";
import { test as base } from "./memory-scoped-coverage";

export type ManuscriptFixtureRoute = Pick<Route, "fulfill" | "abort"> & {
  request(): Pick<Request, "url" | "method" | "postData">;
};
type Handler = (route: ManuscriptFixtureRoute) => Promise<void>;
type ServerState = { handlers: Map<string, Handler>; drain(): Promise<void> };
const owners = new WeakMap<BrowserContext, { owner: string; server: ServerState }>();

export async function registerManuscriptApi(page: Page, handler: Handler) {
  const registration = owners.get(page.context());
  if (!registration) throw new Error("Manuscript HTTP fixture owner is missing");
  registration.server.handlers.set(registration.owner, handler);
  await page.context().route("**/api/v1/**", handler);
}

// Chromium unload keepalive may bypass route interception. Both transports use the
// same per-context handler/state; cookies prevent a late write entering the next test.
export const test = base.extend<{}, { manuscriptServer: ServerState }>({
  manuscriptServer: [async ({}, use) => {
    const root = mkdtempSync(path.join(tmpdir(), "jippeel-manuscript-http-"));
    const violations = path.join(root, "violations.jsonl");
    const handlers = new Map<string, Handler>();
    const pending = new Set<Promise<void>>();
    const config = fixtureConfig(violations);
    const server = await createServer({
      ...config,
      configFile: false,
      server: { host: "127.0.0.1", port: 15225, strictPort: true },
      plugins: [{
        name: "owned-manuscript-http",
        enforce: "pre",
        configureServer(vite) {
          vite.middlewares.use((request, response, next) => {
            const pathname = new URL(request.url ?? "/", "http://fixture.invalid").pathname;
            if (!pathname.startsWith("/api/")) return next();
            const owner = request.headers.cookie?.split("; ").find((cookie) => cookie.startsWith("jippeel_fixture_owner="))?.split("=")[1];
            const handler = owner ? handlers.get(owner) : undefined;
            // Only the known unload endpoint may use the HTTP escape transport.
            if (!handler || request.method !== "PUT" || !/^\/api\/v1\/chapters\/\d+\/content$/.test(pathname)) return next();
            const task = (async () => {
              try {
                const chunks: Buffer[] = [];
                for await (const chunk of request) chunks.push(Buffer.from(chunk));
                const body = Buffer.concat(chunks).toString("utf8");
                const completed = new Promise<void>((resolve) => response.once("close", resolve));
                await handler({
                  request: () => ({ url: () => `http://127.0.0.1:15225${request.url}`, method: () => request.method!, postData: () => body }),
                  fulfill: async (options = {}) => {
                    response.statusCode = options.status ?? 200;
                    for (const [key, value] of Object.entries(options.headers ?? {})) response.setHeader(key, value);
                    if (options.contentType) response.setHeader("Content-Type", options.contentType);
                    if (options.json !== undefined) response.setHeader("Content-Type", "application/json");
                    response.end(options.json === undefined ? options.body : JSON.stringify(options.json));
                  },
                  abort: async () => { response.destroy(); },
                });
                await completed;
              } catch {
                appendFileSync(violations, JSON.stringify({ method: request.method, path: pathname }) + "\n");
                response.statusCode = 500;
                response.end("Manuscript fixture handler failed");
              }
            })();
            pending.add(task);
            void task.finally(() => pending.delete(task));
          });
        },
      }, ...(config.plugins ?? [])],
    });
    const state = { handlers, drain: async () => { await Promise.all([...pending]); } };
    await server.listen();
    console.log(`Owned manuscript fixture started: 127.0.0.1:15225; proxy=${JSON.stringify(server.config.server.proxy ?? {})}; latch=${violations}`);
    try { await use(state); }
    finally {
      await state.drain();
      await server.close();
      const escaped = existsSync(violations) ? readFileSync(violations, "utf8") : "";
      console.log(`Owned manuscript fixture closed; ${escaped ? "FAILED" : "no escapes"}; latch=${violations}`);
      if (escaped) throw new Error(`Unmocked manuscript HTTP requests:\n${escaped}`);
    }
  }, { scope: "worker" }],
  context: async ({ context, manuscriptServer }, use) => {
    const owner = randomUUID();
    owners.set(context, { owner, server: manuscriptServer });
    await context.addCookies([{ name: "jippeel_fixture_owner", value: owner, url: "http://127.0.0.1:15225", httpOnly: true, sameSite: "Strict" }]);
    try { await use(context); }
    finally {
      await context.close();
      await manuscriptServer.drain();
      manuscriptServer.handlers.delete(owner);
      owners.delete(context);
    }
  },
});
