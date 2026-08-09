import { test, expect } from "./fixtures/test";
import { activatePaidLicense, gotoResults, openTab } from "./fixtures/helpers";
import { SALA_CON_USO } from "./fixtures/payloads";

test.describe("Diseño y tratamiento PAID", () => {
  test.beforeEach(async ({ page }) => {
    await gotoResults(page, SALA_CON_USO);
    await activatePaidLicense(page);
    await openTab(page, "Diseño");
  });

  test("verifica un tratamiento contra la sala actual", async ({ page }) => {
    await page.getByRole("tab", { name: "Verificar plan" }).click();
    await page.locator("#treatment-area").fill("12");
    await page.getByRole("button", { name: "Verificar plan" }).click();
    const result = page.getByText("Diagnóstico de tratamiento").locator("..");
    await expect(result).toContainText("predicted_rt60_s", { timeout: 20_000 });
    await expect(result).toContainText("all_bands_meet");
  });

  test("calcula absorbente poroso y expone límites de validez", async ({ page }) => {
    await page.getByRole("tab", { name: "Absorbentes" }).click();
    await page.locator("#abs-poroso-espesor").fill("0.1");
    await page.locator("#abs-poroso-flow").fill("8000");
    await page.getByRole("button", { name: "Predecir α(f)" }).click();
    await expect(page.getByText("Modelo y límites de validez")).toBeVisible();
    const alpha500 = Number(await page.getByLabel("Coeficientes de absorción calculados").locator("tbody td").nth(2).textContent());
    expect(alpha500).toBeGreaterThan(0);
    await expect(page.getByText("Ver datos y diagnósticos completos")).toBeVisible();
  });

  test("genera QRD con diagnóstico de manufacturabilidad", async ({ page }) => {
    await page.getByRole("tab", { name: "Difusores" }).click();
    await page.locator("#dif-qrd-freq").fill("800");
    await page.locator("#dif-qrd-n").fill("13");
    await page.getByRole("button", { name: "Calcular difusor" }).click();
    const result = page.getByText("Construcción, rango útil y manufacturabilidad").locator("..");
    await expect(result).toContainText("design freq hz");
    await result.getByText("Ver datos y diagnósticos completos").click();
    await expect(result.locator("pre")).toContainText("manufacturability");
  });
});
