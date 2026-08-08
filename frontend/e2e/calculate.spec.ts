import { test, expect } from "@playwright/test";
import { fillRoom } from "./fixtures/helpers";

test.describe("Calculation flow", () => {
  test("fills form and navigates to results page", async ({ page }) => {
    await page.goto("/");
    await fillRoom(page, { largo: "8.5", ancho: "6.0", alto: "3.0" });
    await page.getByRole("button", { name: "Calcular" }).click();
    await expect(page).toHaveURL(/\/results/, { timeout: 10000 });
  });

  test("shows 4 summary cards after calculation", async ({ page }) => {
    await page.goto("/");
    await fillRoom(page, { largo: "8.5", ancho: "6.0", alto: "3.0" });
    await page.getByRole("button", { name: "Calcular" }).click();
    await expect(page.locator("text=RT60 Promedio")).toBeVisible({ timeout: 15000 });
    await expect(page.locator("text=Schroeder")).toBeVisible();
    await expect(page.locator("text=ancho modal")).toBeVisible();
    await expect(page.locator("text=Modos totales")).toBeVisible();
  });

  test("encodes request as base64 query param", async ({ page }) => {
    await page.goto("/");
    await fillRoom(page, { largo: "8.5", ancho: "6.0", alto: "3.0" });
    await page.getByRole("button", { name: "Calcular" }).click();
    await expect(page).toHaveURL(/\/results\?data=/, { timeout: 10000 });
    const match = page.url().match(/data=([^&]+)/);
    expect(match).not.toBeNull();
    expect(() => JSON.parse(atob(match![1]))).not.toThrow();
  });

  test("shows RT60 table data after calculation", async ({ page }) => {
    await page.goto("/");
    await fillRoom(page, { largo: "8.5", ancho: "6.0", alto: "3.0" });
    await page.getByRole("button", { name: "Calcular" }).click();
    await expect(page.locator("text=RT60 por Banda de Octava")).toBeVisible({ timeout: 15000 });
  });
});
