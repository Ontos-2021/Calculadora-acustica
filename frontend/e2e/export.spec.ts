import { test, expect } from "@playwright/test";
import { gotoResults } from "./fixtures/helpers";
import { SALA_BASE } from "./fixtures/payloads";

test.describe("Export actions", () => {
  test.beforeEach(async ({ page }) => {
    await gotoResults(page, SALA_BASE);
  });

  test("CSV button triggers download", async ({ page }) => {
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: "Exportar CSV" }).click(),
    ]);
    expect(download.suggestedFilename()).toContain(".csv");
  });

  test("JSON button triggers download", async ({ page }) => {
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: "Exportar JSON" }).click(),
    ]);
    expect(download.suggestedFilename()).toContain(".json");
  });

  test("PDF download link is visible", async ({ page }) => {
    const pdfLink = page.locator('a[download="informe-acustico.pdf"]');
    await expect(pdfLink).toBeVisible();
  });
});
