import { test, expect } from "@playwright/test";
import { gotoResults, openTab } from "./fixtures/helpers";
import { SALA_BASE } from "./fixtures/payloads";

test.describe("Pressure tab", () => {
  test.beforeEach(async ({ page }) => {
    await gotoResults(page, SALA_BASE);
    await openTab(page, "Presión");
  });

  test("renders pressure heatmap", async ({ page }) => {
    await expect(page.getByText("Mapa de Presión Modal")).toBeVisible({ timeout: 10000 });
    await expect(page.locator(".echarts-for-react canvas")).toBeVisible();
  });

  test("mode selector changes options", async ({ page }) => {
    const select = page.locator("#presion-modo");
    const options = await select.locator("option").allTextContents();
    expect(options.length).toBeGreaterThan(1);
    expect(options[0]).toBe("Acumulado (todos los modos)");
  });

  test("frequency slider adjusts max frequency", async ({ page }) => {
    const slider = page.locator("#presion-fmax");
    await slider.fill("200");
    await expect(page.getByText("Frecuencia máxima: 200 Hz")).toBeVisible();
  });

  test("listening position sliders update values", async ({ page }) => {
    await expect(page.getByText("Posición de Escucha Interactiva")).toBeVisible();
    const xSlider = page.locator("#escucha-x");
    const ySlider = page.locator("#escucha-y");
    await xSlider.fill("3");
    await ySlider.fill("2");
    await expect(page.getByText(/X: 3\.0\d m/)).toBeVisible();
  });
});
