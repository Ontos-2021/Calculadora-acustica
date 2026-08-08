import { test, expect } from "@playwright/test";
import { gotoResults, openTab } from "./fixtures/helpers";
import { SALA_BASE } from "./fixtures/payloads";

test.describe("Isolation tab", () => {
  test.beforeEach(async ({ page }) => {
    await gotoResults(page, SALA_BASE);
    await openTab(page, "Aislamiento");
  });

  test("single panel calculator", async ({ page }) => {
    await expect(page.getByText("Aislamiento acústico")).toBeVisible();
    await page.locator("#aisl-simple-masa").fill("100");
    await page.locator("#aisl-simple-espesor").fill("0.15");
    await page.getByRole("button", { name: "Calcular" }).click();
    await page.waitForTimeout(1000);
    await expect(page.getByRole("button", { name: "Calcular" })).toBeEnabled();
  });

  test("double panel calculator with stud checkbox", async ({ page }) => {
    await page.getByRole("button", { name: "Doble hoja" }).click();
    await page.locator("#aisl-doble-m1").fill("50");
    await page.locator("#aisl-doble-m2").fill("30");
    await page.locator("#aisl-doble-camara").fill("0.15");
    await page.locator("#aisl-doble-stud").check();
    await expect(page.locator("#aisl-doble-stud")).toBeChecked();
    await page.getByRole("button", { name: "Calcular" }).click();
    await page.waitForTimeout(1000);
    await expect(page.getByRole("button", { name: "Calcular" })).toBeEnabled();
  });

  test("NC calculator", async ({ page }) => {
    await page.getByRole("button", { name: "Ruido NC" }).click();
    await page.locator("#aisl-nc-125").fill("55");
    await page.locator("#aisl-nc-500").fill("45");
    await page.locator("#aisl-nc-4000").fill("30");
    await page.getByRole("button", { name: "Calcular" }).click();
    await page.waitForTimeout(1000);
    await expect(page.getByRole("button", { name: "Calcular" })).toBeEnabled();
  });
});
