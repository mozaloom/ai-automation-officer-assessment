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

async function login(page: Page) {
  const { email, password } = credentials();
  await page.goto("/login/");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard\/?$/);
}

const settle = (page: Page) => page.waitForTimeout(1200); // let entrance animations finish before screenshots
const num = (n: number) => new Intl.NumberFormat("en-US").format(n);

test("unauthenticated visitors are sent to the sign-in page", async ({ page }) => {
  await page.goto("/dashboard/");
  await expect(page).toHaveURL(/\/login\/\?next=/);
  await settle(page);
  await page.screenshot({ path: path.join(SHOTS, "01-login.png"), fullPage: true });
});

test("a wrong password shows a clear error and stays on the page", async ({ page }) => {
  await page.goto("/login/");
  await page.getByLabel("Email").fill(credentials().email);
  await page.getByLabel("Password", { exact: true }).fill("definitely-wrong-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText("Incorrect email or password.")).toBeVisible();
  await expect(page).toHaveURL(/\/login\//);
});

test("dashboard shows the CSV numbers and filters narrow them", async ({ page }) => {
  const t = truth();
  await login(page);
  await expect(page.getByTestId("kpi-listings")).toHaveText(num(t.total));
  await expect(page.getByTestId("kpi-in-stock")).toHaveText(num(t.inStock));
  await expect(page.getByTestId("kpi-low-stock")).toHaveText(num(t.low));
  await expect(page.getByTestId("kpi-out-of-stock")).toHaveText(num(t.out));
  await expect(page.getByTestId("as-of")).toContainText("25 Aug 2026");
  await expect(page.getByRole("heading", { name: "Availability by city" })).toBeVisible();
  await settle(page);
  await page.screenshot({ path: path.join(SHOTS, "02-dashboard.png"), fullPage: true });

  await page.getByLabel("City", { exact: true }).selectOption("Amman");
  await expect(page.getByTestId("kpi-listings")).toHaveText(num(t.amman));
  await settle(page);
  await page.screenshot({ path: path.join(SHOTS, "03-dashboard-amman.png"), fullPage: true });
  await page.getByRole("button", { name: "Reset" }).click();
  await expect(page.getByTestId("kpi-listings")).toHaveText(num(t.total));
});

test("the assistant answers from the records and asks when a term is ambiguous", async ({ page }) => {
  const t = truth();
  await login(page);
  await page.getByRole("link", { name: "Assistant" }).first().click();
  await expect(page).toHaveURL(/\/assistant\/?$/);

  await page.getByRole("button", { name: "Where can I buy Olive Oil Extra Virgin in Amman?" }).click();
  const records = page.getByTestId("records");
  await expect(records).toBeVisible({ timeout: 60_000 });
  await expect(records).toContainText(`Showing ${t.oliveAmman} of ${t.oliveAmman}`);
  await expect(records.locator("tbody tr")).toHaveCount(t.oliveAmman);
  await settle(page);
  await page.screenshot({ path: path.join(SHOTS, "04-assistant-answer.png"), fullPage: true });

  await page.getByRole("button", { name: "New chat" }).click();
  await page.getByLabel("Your question").fill("Where can I buy tea?");
  await page.getByRole("button", { name: "Send question" }).click();
  await expect(page.getByRole("log")).toContainText(/black tea|green tea/i, { timeout: 60_000 });
  await expect(page.getByTestId("records")).toHaveCount(0);
  await page.getByLabel("Your question").fill("Black Tea Bags");
  await page.getByRole("button", { name: "Send question" }).click();
  await expect(page.getByTestId("records")).toBeVisible({ timeout: 60_000 });
  await settle(page);
  await page.screenshot({ path: path.join(SHOTS, "05-assistant-clarification.png"), fullPage: true });
});

test("signing out returns to the sign-in page and protects the app again", async ({ page }) => {
  await login(page);
  await page.getByRole("button", { name: "Sign out" }).first().click();
  await expect(page).toHaveURL(/\/login\/?$/);
  await page.goto("/dashboard/");
  await expect(page).toHaveURL(/\/login\//);
});

test("works at phone width with the bottom navigation", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page);
  await expect(page.getByRole("navigation", { name: "Mobile navigation" })).toBeVisible();
  await expect(page.getByTestId("kpi-listings")).toBeVisible();
  await settle(page);
  await page.screenshot({ path: path.join(SHOTS, "06-mobile-dashboard.png"), fullPage: true });
});
