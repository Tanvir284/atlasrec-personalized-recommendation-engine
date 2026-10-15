const { test, expect } = require("@playwright/test");
test.skip(process.env.RETAIL !== "1", "Requires installed real retail catalog");

async function catalog(page) {
  const response = await page.request.get("/api/v1/products?limit=60");
  expect(response.ok()).toBeTruthy();
  return (await response.json()).items;
}
async function noOverflow(page) {
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
  ).toBeTruthy();
}
test("real catalog provenance, trained predictions and actual photographs", async ({
  page,
}, testInfo) => {
  if (testInfo.project.name === "desktop")
    await page.setViewportSize({ width: 1440, height: 1000 });
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  const info = await (await page.request.get("/api/v1/catalog/info")).json();
  expect(info.synthetic).toBe(false);
  expect(info.historical_interactions).toBeGreaterThan(1000);
  expect(info.historical_reviewers).toBeGreaterThan(100);
  expect(info.personalization.status).toBe("ready");
  await page.goto("/");
  await expect(page.locator(".department-nav")).not.toContainText("Unknown");
  await expect(page.locator(".source-hero-products img").first()).toBeVisible();
  await expect
    .poll(
      () =>
        page
          .locator(".source-hero-products img")
          .evaluateAll(images => images.filter(i => i.complete && i.naturalWidth > 0).length),
      { timeout: 30000 },
    )
    .toBeGreaterThanOrEqual(2);
  await expect(page.locator('main img[src$=".svg"]')).toHaveCount(0);
  await expect(page.locator(".product-card").first()).toBeVisible();
  await noOverflow(page);
  await page.screenshot({
    path: `docs/evidence/retail-home-${testInfo.project.name}.png`,
    fullPage: true,
    scale: "css",
  });
  await page.screenshot({
    path: `docs/evidence/retail-home-${testInfo.project.name}-viewport.png`,
    scale: "css",
  });
  expect(errors).toEqual([]);
});
test("real search, category and source product details work", async ({ page }, testInfo) => {
  const items = await catalog(page),
    product = items.find(p => p.image && p.title.length > 8);
  expect(product.id).not.toMatch(/^demo-/);
  const query = product.title.split(/\s+/).filter(Boolean).slice(0, 2).join(" ");
  await page.goto(
    "/catalog?q=" + encodeURIComponent(query) + "&category=" + encodeURIComponent(product.category),
  );
  await expect(page.locator(".product-card").first()).toBeVisible();
  const results = await (
    await page.request.get(
      "/api/v1/products?q=" +
        encodeURIComponent(query) +
        "&category=" +
        encodeURIComponent(product.category),
    )
  ).json();
  expect(
    results.items.every(
      p => p.category === product.category && p.title.toLowerCase().includes(query.toLowerCase()),
    ),
  ).toBeTruthy();
  await noOverflow(page);
  await page.screenshot({
    path: `docs/evidence/retail-catalog-${testInfo.project.name}.png`,
    fullPage: true,
  });
  await page.goto("/products/" + product.id);
  await expect(page.getByRole("heading", { name: product.title, exact: true })).toBeVisible();
  await expect
    .poll(
      () =>
        page
          .locator(".product-gallery img")
          .evaluateAll(images => images.some(i => i.complete && i.naturalWidth > 0)),
      { timeout: 30000 },
    )
    .toBe(true);
  await expect(page.locator(".price-caption")).toContainText(
    product.price == null ? "no listed price" : "Historical source price",
  );
  await noOverflow(page);
  await page.screenshot({
    path: `docs/evidence/retail-product-${testInfo.project.name}.png`,
    fullPage: true,
  });
});
test("real account feedback persists and updates served recommendations", async ({ page }) => {
  const items = await catalog(page),
    product = items.find(p => p.image);
  const email = `retail-qa-${Date.now()}-${test.info().project.name}@example.test`;
  await page.goto("/register");
  await page.getByLabel("Your name").fill("AtlasRec verification");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("RetailVerification!2026");
  await page.getByRole("button", { name: "Create account", exact: true }).click();
  await expect(page).toHaveURL(/profile/);
  require("node:fs").mkdirSync(".cache", { recursive: true });
  require("node:fs").appendFileSync(
    ".cache/retail-qa-users.jsonl",
    JSON.stringify({ email }) + "\n",
  );
  await page.goto("/products/" + product.id);
  await page.getByRole("button", { name: "Save for later", exact: true }).click();
  await expect(page.getByRole("button", { name: "Remove from saved", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Rate 4 out of 5", exact: true }).click();
  await expect(page.locator(".your-rating small")).toContainText("4 out of 5");
  await page.reload();
  await expect(page.locator(".your-rating small")).toContainText("4 out of 5");
  await page.getByRole("button", { name: "Not for me", exact: true }).click();
  await expect
    .poll(async () => {
      const history = await (
        await page.request.get("/api/v1/me/history?item_id=" + product.id)
      ).json();
      return history.some(e => e.kind === "dismiss");
    })
    .toBe(true);
  const recs = await (await page.request.get("/api/v1/recommendations?limit=12")).json();
  expect(recs.model_version).toBeTruthy();
  expect(recs.items.length).toBeGreaterThan(0);
  expect(recs.items.some(p => p.id === product.id)).toBe(false);
});
