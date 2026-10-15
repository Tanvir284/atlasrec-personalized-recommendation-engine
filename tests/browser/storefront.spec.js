const { test, expect } = require("@playwright/test");

test("global search, price filters, sorting and pagination work", async ({ page }, testInfo) => {
  await page.goto("/");
  await page.getByLabel("Search AtlasRec", { exact: true }).fill("Task lamp");
  await page.getByLabel("Search department", { exact: true }).selectOption("Workspace");
  await page.getByRole("button", { name: "Submit product search", exact: true }).click();
  await expect(page).toHaveURL(/category=Workspace/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Task lamp");
  await expect(page.locator(".product-card").first()).toBeVisible();
  if (await page.getByRole("button", { name: "Filters", exact: true }).isVisible())
    await page.getByRole("button", { name: "Filters", exact: true }).click();
  await page.getByLabel("Minimum price", { exact: true }).fill("10");
  await page.getByLabel("Maximum price", { exact: true }).fill("150");
  await page.getByRole("button", { name: "Apply filters", exact: true }).click();
  await expect(page).toHaveURL(/max_price=150/);
  await page.getByLabel("Sort products", { exact: true }).selectOption("price_desc");
  await expect(page).toHaveURL(/sort=price_desc/);
  await expect(page.locator(".product-card").first()).toBeVisible();
  const response = await page.request.get("/api/v1/products" + new URL(page.url()).search);
  const data = await response.json();
  expect(data.items.length).toBeGreaterThan(0);
  expect(
    data.items.every(
      product =>
        product.category === "Workspace" &&
        product.title.includes("Task lamp") &&
        product.price >= 10 &&
        product.price <= 150,
    ),
  ).toBe(true);
  expect(data.items.map(p => p.price)).toEqual(data.items.map(p => p.price).sort((a, b) => b - a));
  await page.goto("/catalog?category=Workspace");
  await expect(page.locator(".product-card")).toHaveCount(20);
  const firstHref = await page.locator(".product-title").first().getAttribute("href");
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await expect(page).toHaveURL(/page=2/);
  await expect(page.locator(".product-title").first()).not.toHaveAttribute("href", firstHref);
  await page.goto("/catalog?category=Workspace");
  await expect(page.locator(".product-card")).toHaveCount(20);
  await page.screenshot({
    path: "docs/evidence/storefront-catalog-" + testInfo.project.name + ".png",
    fullPage: true,
  });
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
});

test("department drawer supports navigation and keyboard close", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Departments", exact: true }).click();
  const drawer = page.locator(".department-drawer");
  await expect(drawer).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(drawer).not.toBeVisible();
  await page.getByRole("button", { name: "Departments", exact: true }).click();
  await drawer.getByRole("link", { name: /^Home\b/ }).click();
  await expect(page).toHaveURL(/category=Home/);
  await expect(drawer).not.toBeVisible();
  await expect(page.getByRole("heading", { level: 1, name: "Home", exact: true })).toBeVisible();
});

test("guest save returns through login, ratings persist, and image zoom works", async ({
  page,
}, testInfo) => {
  const email = "storefront-" + Date.now() + "@example.com",
    password = "Storefront!2026";
  await page.goto("/register");
  await page.getByLabel("Your name").fill("Storefront Shopper");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Create account", exact: true }).click();
  await expect(page).toHaveURL(/profile/);
  await Promise.all([
    page.waitForResponse(
      response => response.url().endsWith("/auth/logout") && response.status() === 200,
    ),
    page.getByRole("button", { name: "Log out", exact: true }).click(),
  ]);
  await page.goto("/catalog");
  const card = page.locator(".product-card").first();
  await expect(card).toBeVisible();
  const href = await card.locator(".product-title").getAttribute("href");
  await card.getByRole("button", { name: /^Save / }).click();
  await expect(page).toHaveURL(/login\?next=/);
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(href + "$"));
  await expect(page.getByRole("button", { name: "Save for later", exact: true })).toBeEnabled();
  await Promise.all([
    page.waitForResponse(
      response =>
        response.url().includes("/favorites/") &&
        response.request().method() === "PUT" &&
        response.status() === 200,
    ),
    page.getByRole("button", { name: "Save for later", exact: true }).click(),
  ]);
  await expect(page.getByRole("button", { name: "Remove from saved", exact: true })).toBeVisible();
  await expect(page.locator(".saved-icon b")).toHaveText("1");
  await Promise.all([
    page.waitForResponse(
      response =>
        response.url().endsWith("/events") &&
        response.request().method() === "POST" &&
        response.request().postDataJSON()?.kind === "rating" &&
        response.status() === 200,
    ),
    page.getByRole("button", { name: "Rate 4 out of 5", exact: true }).click(),
  ]);
  await expect(page.getByRole("button", { name: "Rate 4 out of 5", exact: true })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await page.reload();
  await expect(page.getByRole("button", { name: "Rate 4 out of 5", exact: true })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await page.getByRole("button", { name: "Enlarge product image", exact: true }).click();
  await expect(
    page.getByRole("dialog", { name: "Expanded product image", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close expanded image", exact: true }).click();
  await expect(
    page.getByRole("dialog", { name: "Expanded product image", exact: true }),
  ).not.toBeVisible();
  await page.locator("#related-products .product-title").first().click();
  await expect(page).not.toHaveURL(new RegExp(href + "$"));
  await expect(page.getByRole("button", { name: "Rate 4 out of 5", exact: true })).toHaveAttribute(
    "aria-pressed",
    "false",
  );
  await page.goto(href);
  await expect(page.getByRole("button", { name: "Rate 4 out of 5", exact: true })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await page.screenshot({
    path: "docs/evidence/storefront-product-" + testInfo.project.name + ".png",
    fullPage: true,
  });
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
});

test("slow home scripts hydrate without replacing the storefront", async ({ page }) => {
  const errors = [];
  let delayed = 0;
  page.on("pageerror", error => errors.push(error.message));
  await page.route("**/_next/static/chunks/**", async route => {
    const response = await route.fetch(),
      body = await response.text(),
      headers = { ...response.headers() };
    if (body.includes("Everyday essentials.")) {
      delayed++;
      await new Promise(resolve => setTimeout(resolve, 1500));
    }
    delete headers["content-encoding"];
    delete headers["content-length"];
    await route.fulfill({ response, headers, body });
  });
  await page.goto("/");
  await expect(page.locator(".department-card")).toHaveCount(4);
  await expect(page.locator(".product-grid")).toHaveCount(2);
  expect(delayed).toBeGreaterThan(0);
  expect(errors).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(
    page.viewportSize().width,
  );
});

test("incomplete API responses show a retry state and recover", async ({ page }) => {
  const errors = [];
  let interrupted = 0;
  page.on("pageerror", error => errors.push(error.message));
  await page.route("**/api/v1/admin/experiments", async route => {
    if (interrupted < 2) {
      interrupted++;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: '{"interrupted":',
      });
    } else await route.continue();
  });
  await page.goto("/login?next=" + encodeURIComponent("/admin/experiments"));
  await page.getByLabel("Email address").fill("admin@atlasrec.local");
  await page.getByLabel("Password", { exact: true }).fill("AtlasDemo!2026");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/admin\/experiments/);
  await expect(
    page.getByRole("heading", { name: "We couldn't load this", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("The service returned an incomplete response. Please try again.", {
      exact: true,
    }),
  ).toBeVisible();
  expect(interrupted).toBe(2);
  await page.getByRole("button", { name: "Try again", exact: true }).click();
  await expect(page.locator("tbody tr").first()).toBeVisible();
  expect(errors).toEqual([]);
});

test("a delayed product view retries with the same event identity", async ({ page }) => {
  const attempts = [];
  let committed = false;
  await page.route("**/api/v1/events", async route => {
    const body = route.request().postDataJSON();
    if (body?.kind === "view" && body.item_id === "demo-0193") {
      attempts.push(body.id);
      if (attempts.length === 1) {
        await route.fulfill({
          status: 503,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Simulated temporary response loss" }),
        });
        return;
      }
    }
    await route.continue();
  });
  page.on("response", response => {
    if (
      response.url().endsWith("/events") &&
      response.request().method() === "POST" &&
      response.request().postDataJSON()?.kind === "view" &&
      response.request().postDataJSON()?.item_id === "demo-0193" &&
      response.status() === 200
    )
      committed = true;
  });
  await page.goto("/products/demo-0193");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect.poll(() => committed).toBe(true);
  expect(attempts).toHaveLength(2);
  expect(attempts[0]).toBe(attempts[1]);
});
