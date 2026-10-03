import { defineConfig, devices } from "@playwright/test";

// BASE_URL defaults to the local dev server; set BASE_URL=https://xpand.medgan.ai to test the deployed app.
export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 30_000 },
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  outputDir: "./test-results",
  use: { baseURL: process.env.BASE_URL ?? "http://localhost:3000", trace: "retain-on-failure", reducedMotion: "reduce", ...devices["Desktop Chrome"] },
});
