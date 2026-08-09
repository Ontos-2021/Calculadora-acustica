import { test, expect } from "./fixtures/test";
import { activatePaidLicense, fillRoom } from "./fixtures/helpers";

test.describe("Página principal y catálogo", () => {
  test.beforeEach(async ({ page }) => { await page.goto("/"); });

  test("muestra formulario anónimo con ambiente y seis superficies", async ({ page }) => {
    await expect(page.locator("#dim-largo")).toBeVisible();
    await fillRoom(page, { largo: "8.5", ancho: "6", alto: "3" });
    await expect(page.locator("#env-temperature")).toHaveValue("20");
    await expect(page.locator("#env-humidity")).toHaveValue("50");
    await expect(page.locator("select[id^='mat-']")).toHaveCount(7); // six surfaces plus category filter
    await expect(page.getByRole("button", { name: "Calcular" })).toBeEnabled();
  });

  test("carga únicamente los ocho materiales FREE sin clave", async ({ page }) => {
    await fillRoom(page, { largo: "8.5", ancho: "6", alto: "3" });
    await page.waitForFunction(() => (document.querySelector("#mat-frente") as HTMLSelectElement)?.options.length === 8);
    await expect(page.locator("#mat-frente option")).toHaveCount(8);
    await expect(page.getByText("Catálogo FREE anónimo")).toBeVisible();
  });

  test("una licencia PAID validada amplía el catálogo y muestra cuotas", async ({ page }) => {
    await activatePaidLicense(page);
    await fillRoom(page, { largo: "8.5", ancho: "6", alto: "3" });
    await page.waitForFunction(() => (document.querySelector("#mat-frente") as HTMLSelectElement)?.options.length > 30);
    await expect(page.getByText("Catálogo completo de la licencia")).toBeVisible();
    await page.getByTestId("license-trigger").click();
    const license = page.getByRole("region", { name: "Licencia y clave API" });
    await license.getByRole("button", { name: "Ver detalle" }).click();
    await expect(license.getByText("Funciones habilitadas")).toBeVisible();
    await expect(license.getByText("solicitudes/min")).toBeVisible();
    await page.keyboard.press("Escape");
  });

  test("recupera materiales incluidos cuando falla la red y permite reintentar", async ({ page }) => {
    test.info().annotations.push({ type: "expected-console-error", description: "ERR_CONNECTION_REFUSED" });
    await page.route("**/api/v1/materials/defaults**", (route) => route.abort("connectionrefused"));
    await page.reload();
    await fillRoom(page, { largo: "8.5", ancho: "6", alto: "3" });
    await expect(page.getByText(/Se usan los materiales FREE incluidos/)).toBeVisible();
    await expect(page.locator("#mat-frente option")).toHaveCount(8);
    await expect(page.getByRole("button", { name: "Reintentar catálogo" })).toBeVisible();
  });

  test("edita coeficientes personalizados con controles etiquetados", async ({ page }) => {
    await fillRoom(page, { largo: "8.5", ancho: "6", alto: "3" });
    await page.getByRole("button", { name: "α personalizado" }).first().click();
    await page.locator("#alpha-frente-500").fill("0.42");
    await expect(page.locator("#alpha-frente-500")).toHaveValue("0.42");
    await page.getByRole("button", { name: "Ocultar α" }).first().click();
    await expect(page.locator("#alpha-frente-500")).not.toBeVisible();
  });

  test("indica conectividad y preparación real del núcleo offline", async ({ page }) => {
    await expect(page.locator("[data-offline-ready]")).toContainText(/Online/);
    await expect(page.locator("[data-offline-ready='true']")).toBeVisible({ timeout: 15_000 });
  });
});
