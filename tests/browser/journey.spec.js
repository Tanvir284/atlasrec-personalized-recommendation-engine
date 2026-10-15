const { test, expect } = require("@playwright/test");
const { waitForChart } = require("./visual-ready");
test("guest to persisted shopper, then protected admin", async ({ page }, testInfo) => {
  const impressions = [];
  page.on("response", r => {
    const request = r.request();
    if (
      r.url().endsWith("/events") &&
      request.method() === "POST" &&
      request.postDataJSON()?.kind === "impression"
    )
      impressions.push(r.status());
  });
  await page.goto("/");
  const recommendationSection = page
    .locator("section")
    .filter({ has: page.getByRole("heading", { name: "A few picks to start with", exact: true }) });
  await expect(recommendationSection.locator(".product-card").first()).toBeVisible();
  await recommendationSection.locator(".product-card").first().scrollIntoViewIfNeeded();
  await expect.poll(() => impressions.length).toBeGreaterThanOrEqual(2);
  expect(impressions.every(status => status === 200)).toBe(true);
  await page.goto("/catalog");
  await expect(page.getByRole("heading", { name: "The catalog" })).toBeVisible();
  await expect(page.locator(".product-card").first()).toBeVisible();
  await page.goto("/register");
  await page.getByLabel("Your name").fill("Browser Owner");
  await page.getByLabel("Email address").fill("browser-" + Date.now() + "@example.com");
  await page.getByLabel("Password", { exact: true }).fill("BrowserTest!2026");
  await page.getByRole("button", { name: "Create account", exact: true }).click();
  await expect(page).toHaveURL(/profile/);
  await page.getByRole("button", { name: "Audio", exact: true }).click();
  await Promise.all([
    page.waitForResponse(
      r =>
        r.url().endsWith("/me/preferences") && r.request().method() === "PUT" && r.status() === 200,
    ),
    page.getByRole("button", { name: "Save interests", exact: true }).click(),
  ]);
  await page.goto("/catalog");
  const first = page.locator(".product-card").first();
  await Promise.all([
    page.waitForResponse(
      r => r.url().includes("/favorites/") && r.request().method() === "PUT" && r.status() === 200,
    ),
    first.getByRole("button", { name: /^Save / }).click(),
  ]);
  await page.goto("/saved");
  await expect(page.locator(".product-card")).toHaveCount(1);
  await page.reload();
  await expect(page.locator(".product-card")).toHaveCount(1);
  const savedHref = await page
    .locator(".product-card h3")
    .first()
    .locator("..")
    .getAttribute("href");
  await page.locator(".product-card h3").first().click();
  await Promise.all([
    page.waitForResponse(
      r =>
        r.url().endsWith("/events") &&
        r.request().method() === "POST" &&
        r.request().postDataJSON()?.kind === "dismiss" &&
        r.status() === 200,
    ),
    page.getByRole("button", { name: "Not for me", exact: true }).click(),
  ]);
  await page.goto("/for-you");
  await expect(page.locator(".product-card").first()).toBeVisible();
  await expect(page.locator('.product-card a[href="' + savedHref + '"]')).toHaveCount(0);
  await page.goto("/admin");
  await expect(page.getByRole("heading", { name: "Access denied", exact: true })).toBeVisible();
  await Promise.all([
    page.waitForResponse(r => r.url().endsWith("/auth/logout") && r.status() === 200),
    page.getByRole("button", { name: "Log out", exact: true }).click(),
  ]);
  await page.goto("/login");
  await page.getByLabel("Email address").fill("admin@atlasrec.local");
  await page.getByLabel("Password", { exact: true }).fill("AtlasDemo!2026");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/for-you/);
  await page.goto("/admin/models");
  await expect(page.getByRole("heading", { name: "Model registry", exact: true })).toBeVisible();
  await expect(page.locator(".active-model h2")).not.toHaveText("Popularity/content fallback");
  await page.goto("/admin/jobs");
  const [queuedResponse] = await Promise.all([
    page.waitForResponse(
      r => r.url().endsWith("/admin/jobs") && r.request().method() === "POST" && r.status() === 202,
    ),
    page.getByRole("button", { name: "Queue training", exact: true }).click(),
  ]);
  const queued = await queuedResponse.json();
  expect(queued.status).toBe("queued");
  const jobRow = page.locator("tbody tr").filter({ hasText: queued.id });
  await expect(jobRow).toBeVisible();
  if (process.env.EXPECT_QUEUE === "1") {
    await expect(jobRow).toContainText("completed", { timeout: 180000 });
  }
  await page.goto("/admin/experiments");
  await expect(
    page.getByRole("heading", { name: "Experiment notebook", exact: true }),
  ).toBeVisible();
  await expect(page.locator("tbody tr").first()).toBeVisible();
  await waitForChart(page);
  await page.screenshot({
    path: "docs/evidence/experiments-" + testInfo.project.name + ".png",
    fullPage: true,
  });
  await page.goto("/admin/monitoring");
  await expect(
    page.getByRole("heading", { name: "System observations", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Requests", { exact: true })).toBeVisible();
  await page.screenshot({
    path: "docs/evidence/admin-" + testInfo.project.name + ".png",
    fullPage: true,
  });
  await page.goto("/");
  await expect(page.locator(".product-card").first()).toBeVisible();
  await page.screenshot({
    path: "docs/evidence/home-" + testInfo.project.name + ".png",
    fullPage: true,
  });
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth,
  );
  expect(overflow).toBe(false);
  const broken = await page
    .locator("img")
    .evaluateAll(imgs => imgs.filter(i => !i.complete || !i.naturalWidth).length);
  expect(broken).toBe(0);
  const text = await page.locator("body").innerText();
  expect(text).not.toMatch(/[\u00c2\u00e2][\u0080-\u00bf\u0153\u20ac]/);
});
