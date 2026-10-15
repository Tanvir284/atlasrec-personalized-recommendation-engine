const { defineConfig, devices } = require("@playwright/test");
module.exports = defineConfig({
  testDir: "./tests/browser",
  timeout: process.env.EXPECT_QUEUE === "1" ? 300000 : 120000,
  expect: { timeout: 15000 },
  fullyParallel: false,
  workers: 1,
  use: { baseURL: process.env.BASE_URL || "http://localhost:3000", trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "phone", use: { ...devices["iPhone 13"], defaultBrowserType: "chromium" } },
  ],
  reporter: [
    ["list"],
    [
      "json",
      {
        outputFile:
          process.env.RETAIL_HOME === "1"
            ? "docs/evidence/retail-home-browser.json"
            : process.env.RETAIL === "1"
              ? "docs/evidence/retail-browser.json"
              : process.env.STOREFRONT === "1"
                ? "docs/evidence/storefront-browser.json"
                : process.env.AUDIT === "1"
                  ? "docs/evidence/bug-audit-browser.json"
                  : "docs/evidence/browser-check.json",
      },
    ],
    ["html", { open: "never" }],
  ],
});
