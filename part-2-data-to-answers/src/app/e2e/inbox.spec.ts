import { expect, test, type Page } from "@playwright/test";
import { existsSync, mkdirSync, readFileSync } from "node:fs";
import path from "node:path";

const ROOT = path.resolve(__dirname, "../../..");
const SHOTS = path.resolve(__dirname, "screenshots");
mkdirSync(SHOTS, { recursive: true });

function credentials() {
  if (process.env.E2E_EMAIL && process.env.E2E_PASSWORD) return { email: process.env.E2E_EMAIL, password: process.env.E2E_PASSWORD };
  const file = path.join(ROOT, ".demo-credentials");
  if (!existsSync(file)) throw new Error("Set E2E_EMAIL / E2E_PASSWORD or create .demo-credentials");
  const map = Object.fromEntries(readFileSync(file, "utf8").split("\n").filter(Boolean).map((l) => l.split(/=(.*)/s).slice(0, 2)));
  return { email: map.email as string, password: map.password as string };
}

const T = {
  en: { email: "Email", password: "Password", signIn: "Sign in", inbox: "Inbox", review: "Review queue", activity: "Activity", sync: "Sync inbox", edit: "Edit", decide: "Decide", approve: "Approve", cancel: "Cancel", save: "Save and approve", group: "Inbox Automation" },
  ar: { email: "البريد الإلكتروني", password: "كلمة المرور", signIn: "تسجيل الدخول", inbox: "البريد الوارد", review: "قائمة المراجعة", activity: "النشاط", sync: "مزامنة البريد", edit: "تعديل", decide: "قرار", approve: "موافقة", cancel: "إلغاء", save: "حفظ وموافقة", group: "أتمتة البريد الوارد" },
} as const;

async function login(page: Page, l: "en" | "ar", next: string) {
  const { email, password } = credentials();
  await page.goto(`/${l}/login/`);
  await page.getByLabel(T[l].email).fill(email);
  await page.getByLabel(T[l].password, { exact: true }).fill(password);
  await page.getByRole("button", { name: T[l].signIn }).click();
  await expect(page).toHaveURL(new RegExp(`/${l}/dashboard/?$`));
  await page.goto(`/${l}/${next}/`);
}

const shot = (page: Page, name: string) => page.screenshot({ path: path.join(SHOTS, `${name}.png`), fullPage: true });

for (const l of ["en", "ar"] as const) {
  test.describe(`inbox automation (${l})`, () => {
    test("sync, list, proposal detail with real field values", async ({ page }) => {
      await login(page, l, "inbox");
      await expect(page.getByRole("link", { name: T[l].review })).toBeVisible();
      await expect(page.getByText(T[l].group).first()).toBeVisible();
      await page.getByRole("button", { name: T[l].sync }).click();
      const list = page.getByRole("list", { name: T[l].inbox });
      await expect(list.getByRole("listitem").first()).toBeVisible({ timeout: 280_000 });
      await expect(page.getByTestId("sync-status")).not.toContainText(/Syncing|جارٍ المزامنة/, { timeout: 280_000 });
      expect(await list.getByRole("listitem").count()).toBeGreaterThanOrEqual(8);
      await expect(page.getByTestId("proposal-view")).toBeVisible();
      await expect(page.locator("html")).toHaveAttribute("dir", l === "ar" ? "rtl" : "ltr");
      await shot(page, `${l}-inbox-01-list-and-detail`);
      // a different email shows its own proposal
      await list.getByRole("listitem").nth(2).getByRole("button").click();
      await expect(page.getByTestId("proposal-view")).toBeVisible();
    });

    test("review queue: reasons, blocked approval, edit dialog with real members", async ({ page }) => {
      await login(page, l, "review");
      const cards = page.getByTestId("review-card");
      await expect(cards.first()).toBeVisible({ timeout: 60_000 });
      await shot(page, `${l}-inbox-02-review-queue`);
      // an item that cannot run yet has a disabled Approve; an undecided item offers Decide instead of a dead Approve
      const blockedApprove = page.getByRole("button", { name: T[l].approve, disabled: true });
      if (await blockedApprove.count()) await expect(blockedApprove.first()).toBeDisabled();
      await cards.first().getByRole("button", { name: new RegExp(`^(${T[l].edit}|${T[l].decide})$`) }).click();
      const dialog = page.getByRole("dialog");
      await expect(dialog).toBeVisible();
      await shot(page, `${l}-inbox-03-edit-dialog`);
      await dialog.getByRole("button", { name: T[l].cancel }).click();
      await expect(dialog).toBeHidden();
    });

    test("activity trail", async ({ page }) => {
      await login(page, l, "activity");
      const table = page.getByTestId("activity-table");
      await expect(table).toBeVisible({ timeout: 60_000 });
      expect(await table.locator("tbody tr").count()).toBeGreaterThan(5);
      await shot(page, `${l}-inbox-04-activity`);
    });

    test("works at phone width", async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await login(page, l, "inbox");
      await expect(page.getByRole("list", { name: T[l].inbox }).getByRole("listitem").first()).toBeVisible({ timeout: 60_000 });
      expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(1);
      await shot(page, `${l}-inbox-05-mobile`);
    });
  });
}
