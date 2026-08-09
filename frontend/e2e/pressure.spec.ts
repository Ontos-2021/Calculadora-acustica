import { test, expect } from "./fixtures/test";
import { gotoResults, openTab } from "./fixtures/helpers";
import { SALA_BASE } from "./fixtures/payloads";

test.describe("Mapa de presión", () => {
  test.beforeEach(async ({ page }) => {
    await gotoResults(page, SALA_BASE);
    await expect(page.getByTestId("engine-source")).toContainText("Verificado por servidor", { timeout: 20_000 });
    await openTab(page, "Presión");
  });

  test("renderiza magnitud RMS acumulada con fallback tabular", async ({ page }) => {
    await expect(page.getByText("Mapa de presión modal")).toBeVisible();
    await expect(page.getByText("Magnitud RMS modal ponderada normalizada")).toBeVisible();
    await expect(page.locator(".echarts-for-react canvas").first()).toBeVisible();
    await page.getByText("Datos accesibles de muestra del mapa").click();
    await expect(page.getByRole("columnheader", { name: "Valor normalizado" })).toBeVisible();
  });

  test("cambiar frecuencia vuelve a solicitar y cambia los datos efectivos", async ({ page }) => {
    await expect(page.getByText("Magnitud RMS modal ponderada normalizada")).toBeVisible({ timeout: 20_000 });
    const slider = page.locator("#presion-fmax");
    await expect(slider).toBeEnabled();
    const requestPromise = page.waitForRequest((request) => request.url().includes("/pressure-map") && request.method() === "POST" && request.postDataJSON().max_freq === 180);
    const responsePromise = page.waitForResponse((response) => response.url().includes("/pressure-map") && response.request().postDataJSON().max_freq === 180);
    await slider.fill("180");
    const [request, response] = await Promise.all([requestPromise, responsePromise]);
    expect(request.postDataJSON().max_freq).toBe(180);
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body.max_freq).toBe(180);
    await expect(page.getByText(/modos hasta 180\.0 Hz/)).toBeVisible();
  });

  test("seleccionar un modo solicita índices y corrige la etiqueta de cantidad", async ({ page }) => {
    const select = page.locator("#presion-modo");
    const option = await select.locator("option").nth(1).getAttribute("value");
    const requestPromise = page.waitForRequest((request) => request.url().includes("/pressure-map") && Boolean(request.postDataJSON()?.mode_indices));
    await select.selectOption(option!);
    const request = await requestPromise;
    expect(request.postDataJSON().mode_indices).toEqual(option!.split(",").map(Number));
    await expect(page.getByText("Presión modal normalizada con signo")).toBeVisible();
  });

  test("muestra recomendación de movimiento y mejora en dB", async ({ page }) => {
    await expect(page.getByRole("region", { name: "Recomendación de posición de escucha" })).toContainText("Posición de escucha más uniforme");
    await expect(page.getByText("Movimiento", { exact: true })).toBeVisible();
    await expect(page.getByText("Mejora modelada", { exact: true })).toBeVisible();
  });
});
