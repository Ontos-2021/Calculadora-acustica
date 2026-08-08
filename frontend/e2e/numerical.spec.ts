import { test, expect } from "@playwright/test";
import { gotoResults, openTab } from "./fixtures/helpers";
import { SALA_BASE } from "./fixtures/payloads";

test.describe("Numerical tab", () => {
  test.beforeEach(async ({ page }) => {
    await gotoResults(page, SALA_BASE);
    await openTab(page, "Numérico");
  });

  test("impedance calculator with wall Z", async ({ page }) => {
    await expect(page.getByText("Métodos numéricos")).toBeVisible();
    await page.locator("#num-largo").fill("5");
    await page.locator("#num-ancho").fill("4");
    await page.locator("#num-alto").fill("3");
    await page.locator("#num-imp-z").fill("5000");
    await page.getByRole("button", { name: "Ejecutar" }).click();
    await page.waitForTimeout(1000);
    await expect(page.getByRole("button", { name: "Ejecutar" })).toBeEnabled();
  });

  test("FEM 2D with exclusion region", async ({ page }) => {
    await page.getByRole("button", { name: "FEM 2D" }).click();
    await page.locator("#num-fem-nx").fill("20");
    await page.locator("#num-fem-ny").fill("20");
    await page.locator("#num-fem-modos").fill("5");
    await page.locator("#num-fem-excluir").fill("1,0,3,2");
    await page.getByRole("button", { name: "Ejecutar" }).click();
    await page.waitForTimeout(1000);
    await expect(page.getByRole("button", { name: "Ejecutar" })).toBeEnabled();
  });

  test("ray tracing", async ({ page }) => {
    await page.getByRole("button", { name: "Ray tracing" }).click();
    await page.locator("#num-ray-rayos").fill("500");
    await page.locator("#num-ray-reflexiones").fill("30");
    await page.getByRole("button", { name: "Ejecutar" }).click();
    await page.waitForTimeout(1000);
    await expect(page.getByRole("button", { name: "Ejecutar" })).toBeEnabled();
  });

  test("hybrid method", async ({ page }) => {
    await page.getByRole("button", { name: "Híbrido" }).click();
    await page.locator("#num-ray-rayos").fill("300");
    await page.locator("#num-ray-reflexiones").fill("20");
    await page.getByRole("button", { name: "Ejecutar" }).click();
    await expect(page.getByRole("button", { name: /Ejecutar|Calculando\.\.\./ }))
      .toBeEnabled({ timeout: 30000 });
  });
});
