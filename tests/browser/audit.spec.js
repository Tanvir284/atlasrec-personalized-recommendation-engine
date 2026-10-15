const { test, expect } = require("@playwright/test");

test("tracked title visits and saves survive lost or rotated CSRF cookies", async ({
  page,
  context,
}) => {
  const email = "audit-" + Date.now() + "@example.com";
  const password = "AuditOwner!2026";
  await page.goto("/register");
  await page.getByLabel("Your name").fill("Audit Owner");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Create account", exact: true }).click();
  await expect(page).toHaveURL(/profile/);
  await page.goto("/catalog");
  const card = page.locator(".product-card").first();
  await expect(card).toBeVisible();
  const href = await card.locator("h3").locator("..").getAttribute("href");
  const item = href.split("/").at(-1);
  const eventResponse = kind =>
    page.waitForResponse(
      response =>
        response.url().endsWith("/events") &&
        response.request().method() === "POST" &&
        response.request().postDataJSON()?.kind === kind &&
        response.request().postDataJSON()?.item_id === item &&
        response.status() === 200,
    );
  await Promise.all([eventResponse("click"), eventResponse("view"), card.locator("h3").click()]);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await context.clearCookies({ name: "atlas_csrf" });
  await Promise.all([
    page.waitForResponse(
      response =>
        response.url().includes("/favorites/" + item) &&
        response.request().method() === "PUT" &&
        response.status() === 200,
    ),
    page.getByRole("button", { name: "Save for later", exact: true }).click(),
  ]);
  await expect(page.getByRole("button", { name: "Remove from saved", exact: true })).toBeVisible();
  const second = await context.newPage();
  await second.goto("/login");
  await second.getByLabel("Email address").fill(email);
  await second.getByLabel("Password", { exact: true }).fill(password);
  await second.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(second).toHaveURL(/for-you/);
  await Promise.all([
    page.waitForResponse(
      response =>
        response.url().includes("/favorites/" + item) &&
        response.request().method() === "DELETE" &&
        response.status() === 200,
    ),
    page.getByRole("button", { name: "Remove from saved", exact: true }).click(),
  ]);
  await expect(page.getByRole("button", { name: "Save for later", exact: true })).toBeVisible();
  const missingEvents = [];
  second.on("request", request => {
    if (
      request.url().endsWith("/events") &&
      request.method() === "POST" &&
      request.postDataJSON()?.item_id === "audit-missing-product"
    )
      missingEvents.push(request.postDataJSON());
  });
  await second.goto("/products/audit-missing-product");
  await expect(
    second.getByRole("heading", { name: "Product not found", exact: true }),
  ).toBeVisible();
  expect(missingEvents).toHaveLength(0);
  await second.close();
});

test("a failed visible impression is retried and recorded", async ({ page }) => {
  let failedItem,
    recorded = false;
  await page.route("**/api/v1/events", async route => {
    const request = route.request();
    const body = request.postDataJSON();
    if (body?.kind === "impression" && !failedItem) {
      failedItem = body.item_id;
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Audit transient failure" }),
      });
    } else await route.continue();
  });
  page.on("response", response => {
    const body = response.request().method() === "POST" ? response.request().postDataJSON() : null;
    if (
      response.url().endsWith("/events") &&
      body?.kind === "impression" &&
      body.item_id === failedItem &&
      response.status() === 200
    )
      recorded = true;
  });
  await page.goto("/for-you");
  await expect(page.locator(".product-card").first()).toBeVisible();
  await page.locator(".product-card").first().scrollIntoViewIfNeeded();
  await expect.poll(() => !!failedItem).toBe(true);
  await expect.poll(() => recorded).toBe(true);
});

test("taste studio intent lens, match DNA x-ray, counterfactual sandbox, side-by-side compare, and ecosystem bundle work", async ({
  page,
}) => {
  const email = "studio-e2e-" + Date.now() + "@example.com";
  await page.goto("/register");
  await page.getByLabel("Your name").fill("Studio Tester");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("StudioTest!2026");
  await page.getByRole("button", { name: "Create account", exact: true }).click();
  await expect(page).toHaveURL(/profile/);
  await expect(page.getByRole("heading", { name: "Your profile", exact: true })).toBeVisible();

  const firstItem = (await (await page.request.get("/api/v1/products?limit=1")).json()).items[0].id;
  await Promise.all([
    page.waitForResponse(
      r =>
        r.url().endsWith("/events") &&
        r.request().method() === "POST" &&
        r.request().postDataJSON()?.kind === "view" &&
        r.status() === 200,
    ),
    page.goto("/products/" + firstItem),
  ]);
  await expect(page.locator(".bundle-box")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Frequently paired together", exact: true }),
  ).toBeVisible();

  await page.goto("/for-you");
  await expect(page.locator(".taste-studio")).toBeVisible();
  await expect(page.locator(".product-card").first()).toBeVisible();

  await page.getByRole("button", { name: "Inspect Match DNA", exact: true }).click();
  await expect(page.locator(".xray-breakdown").first()).toBeVisible();

  await Promise.all([
    page.waitForResponse(r => r.url().includes("intent=hidden_gems") && r.status() === 200),
    page.getByRole("button", { name: /Hidden Gems/ }).click(),
  ]);

  const seedChip = page.locator(".seed-chip").first();
  await expect(seedChip).toBeVisible();
  await Promise.all([
    page.waitForResponse(r => r.url().includes("ignore_items=") && r.status() === 200),
    seedChip.click(),
  ]);

  const compareButtons = page.locator(".compare-toggle");
  await compareButtons.nth(0).click();
  await compareButtons.nth(1).click();
  await expect(page.locator(".compare-matrix")).toBeVisible();
  await expect(page.locator(".compare-matrix th")).toHaveCount(3);

  await expect(page.locator(".bundle-box")).toBeVisible();
  await expect(page.locator(".lane-section").first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
});
