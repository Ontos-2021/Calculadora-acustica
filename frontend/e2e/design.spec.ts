import { test, expect } from "@playwright/test";
import { gotoResults, openTab } from "./fixtures/helpers";
import { SALA_BASE, SALA_CON_USO } from "./fixtures/payloads";

test.describe("Design tab", () => {
  test("inverse design appears when uso is set", async ({ page }) => {
    await gotoResults(page, SALA_CON_USO);
    await openTab(page, "Diseño");
    // Either inverse calc completed or RT60 already meets target
    const timeout = 10000;
    const yaCumple = page.getByText("La sala ya cumple con el RT60 objetivo");
    const invHeading = page.getByRole("heading", { name: "Diseño inverso", exact: true });
    try {
      await yaCumple.waitFor({ state: "visible", timeout });
    } catch {
      await expect(invHeading).toBeVisible({ timeout });
    }
  });

  test("inverse design not shown without uso", async ({ page }) => {
    await gotoResults(page, SALA_BASE);
    await openTab(page, "Diseño");
    await expect(page.locator("text=La sala ya cumple con el RT60 objetivo")).not.toBeVisible();
  });

  test.describe("Absorber calculators", () => {
    test.beforeEach(async ({ page }) => {
      await gotoResults(page, SALA_BASE);
      await openTab(page, "Diseño");
    });

    test("porous calculator predicts alpha", async ({ page }) => {
      await expect(page.getByText("Calculadora de absorbentes")).toBeVisible();
      await page.locator("#abs-poroso-espesor").fill("0.1");
      await page.locator("#abs-poroso-flow").fill("5000");
      await page.locator("#abs-poroso-densidad").fill("50");
      await page.getByRole("button", { name: "Predecir α(f)" }).click();
      await page.waitForTimeout(1500);
      await expect(page.getByRole("button", { name: "Predecir α(f)" })).toBeEnabled();
    });

    test("helmholtz calculator", async ({ page }) => {
      await page.getByRole("button", { name: "Helmholtz" }).click();
      await page.locator("#abs-helmholtz-cuello-area").fill("0.02");
      await page.locator("#abs-helmholtz-cavidad-vol").fill("0.2");
      await page.locator("#abs-helmholtz-cuello-len").fill("0.03");
      await page.locator("#abs-helmholtz-cuello-radio").fill("0.015");
      await page.getByRole("button", { name: "Predecir α(f)" }).click();
      await page.waitForTimeout(1500);
      await expect(page.getByRole("button", { name: "Predecir α(f)" })).toBeEnabled();
    });

    test("membrane calculator", async ({ page }) => {
      await page.getByRole("button", { name: "Membrana" }).click();
      await page.locator("#abs-membrana-masa").fill("15");
      await page.locator("#abs-membrana-camara").fill("0.08");
      await page.getByRole("button", { name: "Predecir α(f)" }).click();
      await page.waitForTimeout(1500);
      await expect(page.getByRole("button", { name: "Predecir α(f)" })).toBeEnabled();
    });
  });

  test.describe("Diffuser calculators", () => {
    test.beforeEach(async ({ page }) => {
      await gotoResults(page, SALA_BASE);
      await openTab(page, "Diseño");
    });

    test("QRD calculator", async ({ page }) => {
      await page.getByRole("button", { name: "QRD (1D)" }).click();
      await page.locator("#dif-qrd-freq").fill("800");
      await page.locator("#dif-qrd-n").fill("13");
      await page.locator("#dif-qrd-ancho").fill("0.04");
      await page.getByRole("button", { name: "Calcular difusor" }).click();
      await page.waitForTimeout(1500);
      await expect(page.getByRole("button", { name: "Calcular difusor" })).toBeEnabled();
    });

    test("Skyline calculator", async ({ page }) => {
      await page.getByRole("button", { name: "Skyline (2D)" }).click();
      await page.locator("#dif-skyline-freq").fill("800");
      await page.locator("#dif-skyline-grid").fill("5");
      await page.locator("#dif-skyline-celda").fill("0.04");
      await page.getByRole("button", { name: "Calcular difusor" }).click();
      await page.waitForTimeout(1500);
      await expect(page.getByRole("button", { name: "Calcular difusor" })).toBeEnabled();
    });
  });
});
