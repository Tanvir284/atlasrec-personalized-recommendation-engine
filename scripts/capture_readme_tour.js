const { chromium, devices } = require("@playwright/test");
const fs = require("node:fs");
const path = require("node:path");

const OUT_DIR = path.join(__dirname, "..", "docs", "screenshots");

async function waitForImages(page) {
  await page.waitForTimeout(350);
  await page.locator("img").evaluateAll(images =>
    Promise.all(
      images.map(image => {
        if (image.loading === "lazy") image.loading = "eager";
        return image.complete
          ? Promise.resolve()
          : new Promise(resolve => {
              image.onload = resolve;
              image.onerror = resolve;
              setTimeout(resolve, 2500);
            });
      }),
    ),
  );
  await page.waitForTimeout(250);
}

(async () => {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  const browser = await chromium.launch({ headless: true });

  try {
    const context = await browser.newContext({
      viewport: { width: 1440, height: 920 },
      deviceScaleFactor: 1.5,
    });
    const page = await context.newPage();

    // 1. Login as Admin
    console.log("Logging in as admin@atlasrec.local...");
    await page.goto("http://localhost:3000/login", { waitUntil: "networkidle" });
    await page.fill('.auth-form input[name="email"]', "admin@atlasrec.local");
    await page.fill('.auth-form input[name="password"]', "AtlasDemo!2026");
    await page.click(".auth-form button");
    await page.waitForURL("**/for-you", { timeout: 15000 });
    await waitForImages(page);

    // 01: Storefront Hero & Department Showcase
    console.log("Capturing 01-storefront-hero.png...");
    await page.goto("http://localhost:3000/", { waitUntil: "networkidle" });
    await page.locator(".department-card").first().waitFor({ timeout: 15000 });
    await waitForImages(page);
    await page.screenshot({ path: path.join(OUT_DIR, "01-storefront-hero.png") });

    // 02: Home Personalized Recommendation Shelves
    console.log("Capturing 02-home-recommendation-shelves.png...");
    const firstShelf = page.locator(".retail-section").nth(1);
    if (await firstShelf.count()) {
      await firstShelf.scrollIntoViewIfNeeded();
      await page.waitForTimeout(300);
    }
    await page.screenshot({ path: path.join(OUT_DIR, "02-home-recommendation-shelves.png") });

    // 03: Catalog Explorer (20,500+ products & 250 departments)
    console.log("Capturing 03-catalog-explorer.png...");
    await page.goto("http://localhost:3000/catalog", { waitUntil: "networkidle" });
    await page.locator(".product-card").first().waitFor({ timeout: 15000 });
    await waitForImages(page);
    await page.screenshot({ path: path.join(OUT_DIR, "03-catalog-explorer.png") });

    // Save 3 items on catalog so Counterfactual Sandbox & Profile stats are rich
    const saveBtns = page.locator('.product-card button:has-text("Save for later")');
    const saveCount = await saveBtns.count();
    for (let i = 0; i < Math.min(3, saveCount); i++) {
      await saveBtns.nth(i).click();
      await page.waitForTimeout(300);
    }

    // 08: Product Detail Page (PDP) with Rating, Feedback Loop & Bundle
    console.log("Capturing 08-product-detail-pdp.png...");
    const firstProductHref = await page.locator(".product-card a").first().getAttribute("href");
    await page.goto("http://localhost:3000" + (firstProductHref || "/products/tech-00001"), {
      waitUntil: "networkidle",
    });
    await page.locator(".product-detail-grid").waitFor({ timeout: 15000 });
    await waitForImages(page);
    // Give a 5-star rating on PDP
    const star5 = page.locator('button[aria-label="Rate 5 out of 5"]');
    if (await star5.count()) {
      await star5.click();
      await page.waitForTimeout(400);
    }
    await page.screenshot({ path: path.join(OUT_DIR, "08-product-detail-pdp.png") });

    // 04: Interactive Taste Studio & What-If Counterfactual Sandbox
    console.log("Capturing 04-taste-studio-counterfactual.png...");
    await page.goto("http://localhost:3000/for-you", { waitUntil: "networkidle" });
    await page.locator(".taste-studio").waitFor({ timeout: 15000 });
    await page.locator(".product-card").first().waitFor({ timeout: 15000 });
    await waitForImages(page);
    const seedChip = page.locator(".seed-chip").first();
    if (await seedChip.count()) {
      await seedChip.click();
      await page.waitForTimeout(600);
    }
    await page.screenshot({ path: path.join(OUT_DIR, "04-taste-studio-counterfactual.png") });

    // 05: Live Match DNA X-Ray Breakdown
    console.log("Capturing 05-match-dna-xray.png...");
    const dnaBtn = page.locator("button", { hasText: "Inspect Match DNA" });
    if (await dnaBtn.count()) {
      await dnaBtn.click();
      await page.waitForTimeout(400);
    }
    const gridEl = page.locator(".product-grid").first();
    await gridEl.scrollIntoViewIfNeeded();
    await page.waitForTimeout(300);
    await page.screenshot({ path: path.join(OUT_DIR, "05-match-dna-xray.png") });

    // 06: AI Side-by-Side Comparison Matrix
    console.log("Capturing 06-ai-side-by-side-compare.png...");
    const compareBtns = page.locator('.product-card button:has-text("Compare")');
    const compareCount = await compareBtns.count();
    for (let i = 0; i < Math.min(3, compareCount); i++) {
      await compareBtns.nth(i).click();
      await page.waitForTimeout(200);
    }
    const compareMatrix = page.locator(".compare-matrix");
    if (await compareMatrix.count()) {
      await compareMatrix.scrollIntoViewIfNeeded();
      await page.waitForTimeout(350);
    }
    await page.screenshot({ path: path.join(OUT_DIR, "06-ai-side-by-side-compare.png") });

    // 07: Smart Ecosystem Bundle Builder
    console.log("Capturing 07-smart-ecosystem-bundle.png...");
    const bundleBox = page.locator(".bundle-box").first();
    if (await bundleBox.count()) {
      await bundleBox.scrollIntoViewIfNeeded();
      await page.waitForTimeout(300);
      await waitForImages(page);
    }
    await page.screenshot({ path: path.join(OUT_DIR, "07-smart-ecosystem-bundle.png") });

    // 09: User Profile & Role Management Hub (/profile)
    console.log("Capturing 09-user-profile-overview.png...");
    await page.goto("http://localhost:3000/profile", { waitUntil: "networkidle" });
    await page.locator(".profile-hub-banner").waitFor({ timeout: 15000 });
    await page.screenshot({ path: path.join(OUT_DIR, "09-user-profile-overview.png") });

    // 10: User Security & Active Sessions Tab
    console.log("Capturing 10-user-security-sessions.png...");
    const secTab = page.locator(".profile-tab-btn", { hasText: "Password & Sessions" });
    if (await secTab.count()) {
      await secTab.click();
      await page.waitForTimeout(300);
    }
    await page.screenshot({ path: path.join(OUT_DIR, "10-user-security-sessions.png") });

    // 11: User Taste & Activity History Privacy Controls
    console.log("Capturing 11-user-taste-activity.png...");
    const actTab = page.locator(".profile-tab-btn", { hasText: "Activity History" });
    if (await actTab.count()) {
      await actTab.click();
      await page.waitForTimeout(300);
    }
    await page.screenshot({ path: path.join(OUT_DIR, "11-user-taste-activity.png") });

    // 12: Admin ML Workbench Overview (/admin)
    console.log("Capturing 12-admin-ml-overview.png...");
    await page.goto("http://localhost:3000/admin", { waitUntil: "networkidle" });
    await page.locator(".stats").waitFor({ timeout: 15000 });
    await page.screenshot({ path: path.join(OUT_DIR, "12-admin-ml-overview.png") });

    // 13: Admin User Management Console & Live User Editor (/admin/users)
    console.log("Capturing 13-admin-user-management.png...");
    await page.goto("http://localhost:3000/admin/users", { waitUntil: "networkidle" });
    await page.locator("table").waitFor({ timeout: 15000 });
    const editBtn = page.locator("table button", { hasText: "Edit" }).first();
    if (await editBtn.count()) {
      await editBtn.click();
      await page.waitForTimeout(300);
    }
    await page.screenshot({ path: path.join(OUT_DIR, "13-admin-user-management.png") });

    // 14: Admin Model Registry & Atomic Promotion/Rollback (/admin/models)
    console.log("Capturing 14-admin-models-experiments.png...");
    await page.goto("http://localhost:3000/admin/models", { waitUntil: "networkidle" });
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(OUT_DIR, "14-admin-models-experiments.png") });

    // 16: Admin Offline Evaluation Experiment Notebook (/admin/experiments)
    console.log("Capturing 16-admin-experiments-chart.png...");
    await page.goto("http://localhost:3000/admin/experiments", { waitUntil: "networkidle" });
    await page.waitForTimeout(600);
    await page.screenshot({ path: path.join(OUT_DIR, "16-admin-experiments-chart.png") });

    // 17: Admin Live Telemetry & Drift Diagnostics (/admin/monitoring)
    console.log("Capturing 17-admin-monitoring-drift.png...");
    await page.goto("http://localhost:3000/admin/monitoring", { waitUntil: "networkidle" });
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(OUT_DIR, "17-admin-monitoring-drift.png") });

    await context.close();

    // 15: Mobile-First Responsive Experience
    console.log("Capturing 15-mobile-responsive-suite.png...");
    const mobileContext = await browser.newContext({
      ...devices["iPhone 13"],
    });
    const mobilePage = await mobileContext.newPage();
    await mobilePage.goto("http://localhost:3000/for-you", { waitUntil: "networkidle" });
    await mobilePage.locator(".taste-studio").waitFor({ timeout: 15000 });
    await waitForImages(mobilePage);
    await mobilePage.screenshot({ path: path.join(OUT_DIR, "15-mobile-responsive-suite.png") });
    await mobileContext.close();

    console.log("All 17 high-resolution screenshots captured successfully!");
  } finally {
    await browser.close();
  }
})();
