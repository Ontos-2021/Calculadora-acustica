import AxeBuilder from "@axe-core/playwright";
import { test, expect } from "./fixtures/test";
import { gotoResults } from "./fixtures/helpers";
import { SALA_BASE } from "./fixtures/payloads";

test.describe("Accesibilidad y respuesta móvil", () => {
  test("no desborda a 320, 375 ni 768 px", async ({ page }) => {
    for (const width of [320, 375, 768]) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto("/");
      await expect(page.locator("#dim-largo")).toBeVisible();
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(overflow, `horizontal overflow at ${width}px`).toBeLessThanOrEqual(1);
    }
    await page.setViewportSize({ width: 320, height: 900 });
    await gotoResults(page, SALA_BASE);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  });

  test("tabs implementan semántica y navegación por flechas", async ({ page }) => {
    await gotoResults(page, SALA_BASE);
    const analysis = page.getByRole("tab", { name: /^Análisis/ });
    await analysis.focus();
    await analysis.press("ArrowRight");
    await expect(page.getByRole("tab", { name: "Presión" })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("tabpanel")).toBeVisible();
  });

  test("axe no detecta impactos serios o críticos", async ({ page }) => {
    await page.goto("/");
    const home = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
    expect(home.violations.filter((violation) => violation.impact === "serious" || violation.impact === "critical")).toEqual([]);
    await gotoResults(page, SALA_BASE);
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
    expect(results.violations.filter((violation) => violation.impact === "serious" || violation.impact === "critical")).toEqual([]);
  });
});
