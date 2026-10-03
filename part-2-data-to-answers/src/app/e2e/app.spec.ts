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

/** Ground truth straight from the CSV, so the test fails if the dashboard drifts from the data. */
function truth() {
  const [header, ...lines] = readFileSync(path.join(ROOT, "data/pos_availability.csv"), "utf8").trim().split(/\r?\n/);
  const cols = header.split(",");
  const rows = lines.map((l) => Object.fromEntries(l.split(",").map((v, i) => [cols[i], v])));
  const count = (s: string, city?: string) => rows.filter((r) => r.availability_status === s && (!city || r.city === city)).length;
  return { total: rows.length, inStock: count("In Stock"), low: count("Low Stock"), out: count("Out of Stock"), amman: rows.filter((r) => r.city === "Amman").length,
           oliveAmman: rows.filter((r) => r.product_name === "Olive Oil Extra Virgin" && r.city === "Amman").length };
}

type Locale = "en" | "ar";
const T = {
  en: { email: "Email", password: "Password", signIn: "Sign in", wrong: "Incorrect email or password.", city: "City", reset: "Reset filters", byCity: "Availability by city", assistant: "Assistant", signOut: "Sign out",
        question: "Your question", newChat: "New chat", send: "Send", mobileNav: "Mobile navigation", sample: "Where can I buy Olive Oil Extra Virgin in Amman?", tea: "Where can I buy tea?", teaFollow: "Black Tea Bags", asOf: "25 Aug 2026", showing: (n: number) => `Showing ${n} of ${n}` },
  ar: { email: "البريد الإلكتروني", password: "كلمة المرور", signIn: "تسجيل الدخول", wrong: "البريد الإلكتروني أو كلمة المرور غير صحيحة.", city: "المدينة", reset: "إعادة ضبط المرشّحات", byCity: "التوافر حسب المدينة", assistant: "المساعد", signOut: "تسجيل الخروج",
        question: "سؤالك", newChat: "محادثة جديدة", send: "إرسال", mobileNav: "التنقل على الجوال", sample: "أين أجد زيت الزيتون البكر الممتاز في عمّان؟", tea: "وين بلاقي شاي؟", teaFollow: "الشاي الأسود أكياس", asOf: "25 آب 2026", showing: (n: number) => `يُعرض ${n} من أصل ${n}` },
} as const;

async function login(page: Page, l: Locale) {
  const { email, password } = credentials();
  await page.goto(`/${l}/login/`);
  await page.getByLabel(T[l].email).fill(email);
  await page.getByLabel(T[l].password, { exact: true }).fill(password);
  await page.getByRole("button", { name: T[l].signIn }).click();
  await expect(page).toHaveURL(new RegExp(`/${l}/dashboard/?$`));
}

const settle = (page: Page) => page.waitForTimeout(600);
const num = (n: number) => new Intl.NumberFormat("en-US").format(n);
const shot = (page: Page, name: string) => page.screenshot({ path: path.join(SHOTS, `${name}.png`), fullPage: true });

test("the root opens in the browser language", async ({ browser }) => {
  for (const [lang, expected] of [["ar-JO", "ar"], ["en-US", "en"]] as const) {
    const context = await browser.newContext({ locale: lang });
    const page = await context.newPage();
    await page.goto("/");
    await expect(page).toHaveURL(new RegExp(`/${expected}/login/`));
    await expect(page.locator("html")).toHaveAttribute("lang", expected);
    await expect(page.locator("html")).toHaveAttribute("dir", expected === "ar" ? "rtl" : "ltr");
    await context.close();
  }
});

test("the language toggle keeps the page and remembers the choice", async ({ page }) => {
  await page.goto("/en/login/");
  await page.getByRole("link", { name: "Switch to Arabic" }).click();
  await expect(page).toHaveURL(/\/ar\/login\/$/);
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await page.goto("/");
  await expect(page).toHaveURL(/\/ar\//);
});

for (const l of ["en", "ar"] as const) {
  test.describe(l, () => {
    test("unauthenticated visitors are sent to the sign-in page, and a wrong password is explained", async ({ page }) => {
      await page.goto(`/${l}/dashboard/`);
      await expect(page).toHaveURL(new RegExp(`/${l}/login/\\?next=`));
      await settle(page);
      await shot(page, `${l}-01-login`);
      await page.getByLabel(T[l].email).fill(credentials().email);
      await page.getByLabel(T[l].password, { exact: true }).fill("definitely-wrong-password");
      await page.getByRole("button", { name: T[l].signIn }).click();
      await expect(page.getByText(T[l].wrong)).toBeVisible();
    });

    test("dashboard shows the CSV numbers; filters narrow them and live in the URL", async ({ page }) => {
      const t = truth();
      await login(page, l);
      await expect(page.getByTestId("kpi-listings")).toHaveText(num(t.total));
      await expect(page.getByTestId("kpi-in-stock")).toHaveText(num(t.inStock));
      await expect(page.getByTestId("kpi-low-stock")).toHaveText(num(t.low));
      await expect(page.getByTestId("kpi-out-of-stock")).toHaveText(num(t.out));
      await expect(page.getByTestId("as-of")).toContainText(T[l].asOf);
      await expect(page.getByRole("heading", { name: T[l].byCity })).toBeVisible();
      await settle(page);
      await shot(page, `${l}-02-dashboard`);
      await page.getByLabel(T[l].city, { exact: true }).selectOption("Amman");
      await expect(page).toHaveURL(/city=Amman/);
      await expect(page.getByTestId("kpi-listings")).toHaveText(num(t.amman));
      await page.getByRole("button", { name: T[l].reset }).click();
      await expect(page.getByTestId("kpi-listings")).toHaveText(num(t.total));
    });

    test("the assistant streams an answer from the records and asks when a term is ambiguous", async ({ page }) => {
      const t = truth();
      await login(page, l);
      await page.getByRole("link", { name: T[l].assistant }).first().click();
      await expect(page).toHaveURL(new RegExp(`/${l}/assistant/?$`));
      await page.getByRole("button", { name: T[l].sample }).click();
      const records = page.getByTestId("records");
      await expect(records).toBeVisible({ timeout: 60_000 });
      await expect(records).toContainText(T[l].showing(t.oliveAmman));
      await expect(records.locator("tbody tr")).toHaveCount(t.oliveAmman);
      await expect(page.getByRole("button", { name: T[l].send })).toBeVisible({ timeout: 60_000 }); // stream finished: Stop is gone
      await settle(page);
      await shot(page, `${l}-03-assistant-answer`);

      await page.getByRole("button", { name: T[l].newChat }).click();
      await page.getByLabel(T[l].question).fill(T[l].tea);
      await page.keyboard.press("Enter");
      await expect(page.getByRole("button", { name: T[l].send })).toBeVisible({ timeout: 60_000 });
      await expect(page.getByTestId("records")).toHaveCount(0);
    });

    test("signing out returns to sign-in and protects the app again", async ({ page }) => {
      await login(page, l);
      await page.getByRole("button", { name: T[l].signOut }).first().click();
      await expect(page).toHaveURL(new RegExp(`/${l}/login/?$`));
      await page.goto(`/${l}/dashboard/`);
      await expect(page).toHaveURL(/\/login\//);
    });

    test("works at phone width with the bottom navigation", async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await login(page, l);
      await expect(page.getByRole("navigation", { name: T[l].mobileNav })).toBeVisible();
      await expect(page.getByTestId("kpi-listings")).toBeVisible();
      await settle(page);
      await shot(page, `${l}-04-mobile-dashboard`);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(overflow).toBeLessThanOrEqual(1); // no horizontal scrolling
    });
  });
}
