import { test, expect } from "@playwright/test";
import { gotoResults } from "./fixtures/helpers";
import { SALA_BASE } from "./fixtures/payloads";

test.describe("Analysis tab", () => {
  test.beforeEach(async ({ page }) => {
    await gotoResults(page, SALA_BASE);
    // "Análisis" is the first tab — should be open by default
  });

  test("renders mode table with data", async ({ page }) => {
    await expect(page.getByRole("heading", { name: /Modos de Resonancia/ })).toBeVisible({ timeout: 10000 });
    const rows = page.locator("table tbody tr");
    expect(await rows.count()).toBeGreaterThan(0);
  });

  test("filters modes by type", async ({ page }) => {
    await page.locator("#modos-tipo").selectOption("axial");
    // After filtering, should still have rows or empty state
    await expect(page.locator("table tbody tr").first().or(page.getByText("No se encontraron"))).toBeVisible();
  });

  test("filters modes by frequency range", async ({ page }) => {
    await page.locator("#modos-fmin").fill("100");
    await page.locator("#modos-fmax").fill("150");
    await expect(page.locator("table tbody tr").first().or(page.getByText("No se encontraron"))).toBeVisible();
  });

  test("shows Bonello verdict", async ({ page }) => {
    await expect(page.getByText("Criterio de Bonello")).toBeVisible();
    await expect(page.getByText("Cumple").or(page.getByText("No cumple"))).toBeVisible();
  });

  test("shows proportions card", async ({ page }) => {
    await expect(page.getByText("Proporciones de Sala")).toBeVisible();
    await expect(page.getByText("Proporción actual:")).toBeVisible();
  });

  test("shows RT60 table with band values", async ({ page }) => {
    await expect(page.getByText("RT60 por Banda de Octava")).toBeVisible();
    await expect(page.getByText("Sabine").first()).toBeVisible();
  });

  test("clicking a mode row selects it", async ({ page }) => {
    const row = page.locator("table tbody tr").first();
    await row.click();
    await expect(row).toHaveClass(/bg-indigo-100/);
  });
});
