import { expect, test } from "@playwright/test";
import path from "node:path";

// Reduced motion is off here on purpose: the sign-in panel waves must really be animating.
test.use({ reducedMotion: "no-preference" });

test("the sign-in panel has moving waves that stop for reduced-motion users", async ({ page }) => {
  await page.goto("/en/login/");
  const wave = page.locator("aside .animate-wave-1").first();
  await expect(wave).toBeVisible();
  const transformAt = () => wave.evaluate((el) => getComputedStyle(el).transform);
  const first = await transformAt();
  await page.waitForTimeout(1200);
  expect(await transformAt()).not.toBe(first); // the layer is sliding
  await page.screenshot({ path: path.join(__dirname, "screenshots", "07-login-waves.png") });

  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.waitForTimeout(300);
  const still = await transformAt();
  await page.waitForTimeout(800);
  expect(await transformAt()).toBe(still); // reduced motion: no movement
});
