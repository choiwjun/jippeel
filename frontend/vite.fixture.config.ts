import { fileURLToPath } from "node:url";
import { appendFileSync } from "node:fs";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// No inherited production proxy. A missed browser mock is a latched suite failure.
export function fixtureConfig(violationsFile: string) {
  return defineConfig({
  plugins: [react(), {
    name: "fixture-api-tripwire",
    configResolved(config) {
      if (Object.keys(config.server.proxy ?? {}).length) throw new Error("Fixture server must not proxy API traffic");
      if (!violationsFile) throw new Error("Fixture API tripwire destination is required");
    },
    configureServer(server) {
      const file = violationsFile;
      server.middlewares.use((request, response, next) => {
        const pathname = new URL(request.url ?? "/", "http://fixture.invalid").pathname;
        if (pathname !== "/api" && !pathname.startsWith("/api/")) return next();
        const violation = JSON.stringify({ method: request.method, path: pathname });
        appendFileSync(file, violation + "\n");
        console.error(`FIXTURE_API_ESCAPE ${violation}`);
        response.statusCode = 500;
        response.end("Unmocked fixture API request");
      });
    },
  }],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
});

}

export default defineConfig(() => fixtureConfig(process.env.JIPPEEL_FIXTURE_API_VIOLATIONS ?? ""));
