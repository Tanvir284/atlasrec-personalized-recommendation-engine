const { chromium, devices } = require("@playwright/test");
const { waitForChart } = require("../tests/browser/visual-ready");
(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    for (const name of ["desktop", "phone"]) {
      const { defaultBrowserType: _browserType, ...phone } = devices["iPhone 13"];
      const context = await browser.newContext({
        baseURL: "http://localhost:3000",
        ...(name === "phone" ? phone : { viewport: { width: 1280, height: 720 } }),
      });
      const token = (await (await context.request.get("/api/v1/auth/csrf")).json()).csrf_token;
      const login = await context.request.post("/api/v1/auth/login", {
        headers: { Origin: "http://localhost:3000", "x-csrf-token": token },
        data: { email: "admin@atlasrec.local", password: "AtlasDemo!2026" },
      });
      if (!login.ok()) throw new Error("Capture login failed: " + login.status());
      const page = await context.newPage();
      await page.goto("/admin/experiments");
      await waitForChart(page);
      await page.screenshot({ path: "docs/evidence/experiments-" + name + ".png", fullPage: true });
      if (await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)) {
        throw new Error("Document overflow in " + name);
      }
      console.log(name + ": captured persisted chart after animation settled");
      await context.close();
    }
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
