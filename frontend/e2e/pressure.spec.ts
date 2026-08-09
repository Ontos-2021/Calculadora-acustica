import { test, expect } from "./fixtures/test";
import { gotoResults, openTab } from "./fixtures/helpers";
import { SALA_BASE } from "./fixtures/payloads";

test.describe("Mapa de presión", () => {
  test.beforeEach(async ({ page }) => { await gotoResults(page, SALA_BASE); await openTab(page, "Presión"); });

  test("renderiza magnitud RMS acumulada con fallback tabular", async ({ page }) => {
    await expect(page.getByText("Mapa de presión modal")).toBeVisible();
    await expect(page.getByText("Magnitud RMS modal ponderada normalizada")).toBeVisible();
    await expect(page.locator(".echarts-for-react canvas").first()).toBeVisible();
    await page.getByText("Datos accesibles de muestra del mapa").click();
    await expect(page.getByRole("columnheader", { name: "Valor normalizado" })).toBeVisible();
  });

  test("cambiar frecuencia vuelve a solicitar y cambia los datos efectivos", async ({ page }) => {
    const responsePromise = page.waitForResponse((response) => response.url().includes("/pressure-map") && response.request().method() === "POST" && response.request().postDataJSON().max_freq === 180);
    await page.locator("#presion-fmax").fill("180");
    const response = await responsePromise;
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body.max_freq).toBe(180);
    await expect(page.getByText(/modos hasta 180\.0 Hz/)).toBeVisible();
  });

  test("seleccionar un modo solicita índices y corrige la etiqueta de cantidad", async ({ page }) => {
    const select = page.locator("#presion-modo");
    const option = await select.locator("option").nth(1).getAttribute("value");
    const responsePromise = page.waitForResponse((response) => response.url().includes("/pressure-map") && response.request().postDataJSON()?.mode_indices);
    await select.selectOption(option!);
    const response = await responsePromise;
    expect((await response.json()).quantity).toBe("signed_normalized_pressure");
    await expect(page.getByText("Presión modal normalizada con signo")).toBeVisible();
  });

  test("muestra recomendación de movimiento y mejora en dB", async ({ page }) => {
    await expect(page.getByText("Recomendación de escucha basada en uniformidad espectral")).toBeVisible();
    await expect(page.getByText("Movimiento", { exact: true })).toBeVisible();
    await expect(page.getByText("Mejora modelada", { exact: true })).toBeVisible();
    await expect(page.getByText(/Confirma la recomendación mediante medición/)).toBeVisible();
  });
});
