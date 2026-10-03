import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const ROOT = path.resolve(__dirname, "..");
const files = (dir: string): string[] =>
  readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name);
    return statSync(full).isDirectory() ? files(full) : /\.tsx?$/.test(name) ? [full] : [];
  });

// Physical left/right utilities do not flip in Arabic. Use the logical ones: ms/me, ps/pe, start/end, text-start/end, rounded-s/e, border-s/e.
const PHYSICAL = /(?<![\w-])(?:-?(?:ml|mr|pl|pr)-(?:\d|\[|px|auto)|(?:left|right)-(?:\d|\[|px|full|1\/2|auto)|-(?:left|right)-\d|text-(?:left|right)\b|float-(?:left|right)|rounded-(?:l|r|tl|tr|bl|br)(?:-|\b)|border-(?:l|r)(?:-|\b)|scroll-(?:ml|mr|pl|pr)-)/;

describe("right-to-left safety", () => {
  const sources = [...files(path.join(ROOT, "components")), ...files(path.join(ROOT, "app")), ...files(path.join(ROOT, "lib"))];
  it("finds the sources to check", () => expect(sources.length).toBeGreaterThan(30));
  it("uses no physical left/right utilities", () => {
    const offenders = sources.flatMap((file) =>
      readFileSync(file, "utf8").split("\n").flatMap((line, i) => {
        const hit = PHYSICAL.exec(line.replace(/\/\/.*$/, ""));
        return hit ? [`${path.relative(ROOT, file)}:${i + 1} ${hit[0]}`] : [];
      }));
    expect(offenders).toEqual([]);
  });
});
