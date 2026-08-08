import { test, expect } from "@playwright/test";
import { gotoResults, openTab } from "./fixtures/helpers";
import { SALA_BASE } from "./fixtures/payloads";

test.describe("Measurement tab", () => {
  test.beforeEach(async ({ page }) => {
    await gotoResults(page, SALA_BASE);
    await openTab(page, "Medición");
  });

  test("ESS calculator with configurable params", async ({ page }) => {
    await expect(page.getByText("Medición y validación")).toBeVisible();
    await page.locator("#med-ess-f1").fill("30");
    await page.locator("#med-ess-f2").fill("18000");
    await page.locator("#med-ess-duracion").fill("2");
    await page.getByRole("button", { name: "Ejecutar" }).click();
    await page.waitForTimeout(1000);
    await expect(page.getByRole("button", { name: "Ejecutar" })).toBeEnabled();
  });

  test("Waterfall with custom IR input", async ({ page }) => {
    await page.getByRole("button", { name: "Waterfall" }).click();
    await page.locator("#med-waterfall-ir").fill("1,0.5,0.2,-0.1,0.05");
    await page.getByRole("button", { name: "Ejecutar" }).click();
    await page.waitForTimeout(1000);
    await expect(page.getByRole("button", { name: "Ejecutar" })).toBeEnabled();
  });

  test("Calibration calculator", async ({ page }) => {
    await page.getByRole("button", { name: "Calibración" }).click();
    await page.locator("#med-cal-banda").selectOption("1000");
    await page.locator("#med-cal-rt60").fill("0.6");
    await page.getByRole("button", { name: "Ejecutar" }).click();
    await page.waitForTimeout(1000);
    await expect(page.getByRole("button", { name: "Ejecutar" })).toBeEnabled();
  });
});
