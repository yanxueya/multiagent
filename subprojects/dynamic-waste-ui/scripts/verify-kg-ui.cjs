/* 用 Playwright 验证知识图谱页面的 schema、事件目录和视口边界。 */
const path = require("path");
const { chromium } = require("playwright");

async function main() {
  const url = process.argv[2] || "http://127.0.0.1:5175/?view=kg";
  const output = path.resolve(process.argv[3] || "artifacts/kg-ui-verification.png");
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || undefined,
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  await page.goto(url, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: /事件日志层/ }).click();
  const definitions = page.locator(".kg-event-definitions details");
  if ((await definitions.count()) !== 7) throw new Error("Expected seven event definitions");
  await definitions.first().locator("summary").click();
  await page.waitForTimeout(300);
  const metrics = await page.evaluate(() => ({
    viewportWidth: window.innerWidth,
    viewportHeight: window.innerHeight,
    documentWidth: document.documentElement.scrollWidth,
    documentHeight: document.documentElement.scrollHeight,
  }));
  if (metrics.documentWidth > metrics.viewportWidth) throw new Error(`Horizontal overflow: ${JSON.stringify(metrics)}`);
  await page.screenshot({ path: output, fullPage: false });
  await page.getByRole("button", { name: /短期记忆层/ }).click();
  const schemaCatalog = page.locator(".kg-schema-catalog");
  if (!(await schemaCatalog.getByText(/UnknownSample · 7 字段/).count())) throw new Error("UnknownSample schema is missing");
  if (!(await schemaCatalog.getByText(/UnknownCluster · 6 字段/).count())) throw new Error("UnknownCluster schema is missing");
  await page.getByRole("button", { name: /长期知识层/ }).click();
  if (!(await page.getByText(/graspability_prior: low \/ medium \/ high/).count())) throw new Error("graspability_prior domain is missing");
  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
  await mobile.goto(url, { waitUntil: "networkidle" });
  const mobileMetrics = await mobile.evaluate(() => ({
    viewportWidth: window.innerWidth,
    documentWidth: document.documentElement.scrollWidth,
  }));
  if (mobileMetrics.documentWidth > mobileMetrics.viewportWidth) throw new Error(`Mobile horizontal overflow: ${JSON.stringify(mobileMetrics)}`);
  await mobile.screenshot({ path: output.replace(/\.png$/i, "-mobile.png"), fullPage: false });
  console.log(JSON.stringify({ url, output, eventDefinitions: 7, unknownSampleFields: 7, unknownClusterFields: 6, metrics, mobileMetrics }));
  await browser.close();
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
