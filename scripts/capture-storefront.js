const { chromium, devices } = require("@playwright/test");
const fs = require("node:fs");
(async () => {
  const browser = await chromium.launch({ headless: true });
  const results = [];
  try {
    for (const [name, options] of [
      ["desktop", { viewport: { width: 1440, height: 1000 } }],
      ["phone", { ...devices["iPhone 13"] }],
      ["small-phone", { viewport: { width: 320, height: 740 }, isMobile: true, hasTouch: true }],
    ]) {
      const context = await browser.newContext(options);
      const page = await context.newPage();
      const errors = [];
      page.on("pageerror", error => errors.push(error.message));
      for (const [label, path] of [
        ["home", "/"],
        ["catalog", "/catalog"],
        ["for-you", "/for-you"],
        ["product", "/products/demo-0193"],
        ["login", "/login"],
      ]) {
        errors.length = 0;
        await page.goto("http://localhost:3000" + path, { waitUntil: "domcontentloaded" });
        if (label === "home") {
          await page.locator(".department-card").first().waitFor();
          await page.locator(".product-grid").nth(1).waitFor();
        }
        if (label === "catalog") await page.locator(".product-card").first().waitFor();
        if (label === "for-you") {
          await page.locator(".taste-studio").waitFor();
          await page.locator(".product-card").first().waitFor();
        }
        if (label === "product") {
          await page.locator(".enlarge-image img").waitFor();
          await page.locator(".product-grid").first().waitFor();
        }
        await page.locator("img").evaluateAll(images =>
          Promise.all(
            images.map(image => {
              if (image.loading === "lazy") image.loading = "eager";
              return image.complete
                ? Promise.resolve()
                : new Promise(resolve => {
                    image.onload = resolve;
                    image.onerror = resolve;
                  });
            }),
          ),
        );
        await page.screenshot({
          scale: "css",
          path: "docs/evidence/storefront-" + label + "-" + name + "-viewport.png",
        });
        if (label === "home" && name !== "small-phone")
          await page.screenshot({
            scale: "css",
            path: "docs/evidence/storefront-home-" + name + ".png",
            fullPage: true,
          });
        const metrics = await page.evaluate(() => ({
          width: innerWidth,
          documentWidth: document.documentElement.scrollWidth,
          brokenImages: [...document.images]
            .filter(image => !image.complete || !image.naturalWidth)
            .map(image => image.src),
        }));
        results.push({
          device: name,
          page: label,
          viewport: options.viewport.width,
          ...metrics,
          errors: [...errors],
        });
      }
      await context.close();
    }
  } finally {
    await browser.close();
  }
  fs.writeFileSync(
    "docs/evidence/storefront-visual.json",
    JSON.stringify({ captured_at: new Date().toISOString(), results }, null, 2) + "\n",
  );
  console.log(JSON.stringify(results));
  if (
    results.some(
      result =>
        result.documentWidth > result.viewport ||
        result.width > result.viewport ||
        result.brokenImages.length ||
        result.errors.length,
    )
  )
    process.exitCode = 1;
})().catch(error => {
  console.error(error);
  process.exit(1);
});
