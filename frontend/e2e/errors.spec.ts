import { test, expect } from "./fixtures/test";
import { encodePayload } from "./fixtures/helpers";
import { SALA_BASE } from "./fixtures/payloads";

test.describe("Errores y recuperación", () => {
  test("explica datos ausentes o base64url malformado", async ({ page }) => {
    await page.goto("/results");
    await expect(page.getByText("No se encontraron datos de cálculo.")).toBeVisible();
    await page.goto("/results?data=not-valid!!!!");
    await expect(page.getByText("Los datos del análisis están dañados o incompletos.")).toBeVisible();
  });

  test("muestra validación 422 y no la disfraza como fallo offline", async ({ page }) => {
    test.info().annotations.push({ type: "expected-console-error", description: "status of 422" });
    await page.goto(`/results?data=${encodePayload({ ...SALA_BASE, largo: 2000 })}`);
    await expect(page.locator("main [role='alert']")).toContainText(/Revisa los datos ingresados|less than or equal/i);
    await expect(page.getByText(/Motor FREE TypeScript/)).not.toBeVisible();
  });

  test("un fallo de red invoca el motor FREE real", async ({ page }) => {
    test.info().annotations.push({ type: "expected-console-error", description: "ERR_CONNECTION_REFUSED" });
    await page.route("**/api/v1/calculate", (route) => route.abort("connectionrefused"));
    await page.route("**/api/v1/pressure-map", (route) => route.abort("connectionrefused"));
    await page.goto(`/results?data=${encodePayload(SALA_BASE)}`);
    await expect(page.getByText("RT60 Promedio")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("engine-source")).toContainText("Motor FREE TypeScript determinista");
    const modeCount = Number(await page.getByText("Modos totales").locator("..").locator("p").nth(1).textContent());
    expect(modeCount).toBeGreaterThan(0);
  });

  test("permite volver desde un error", async ({ page }) => {
    await page.goto("/results");
    await page.getByRole("link", { name: "Volver" }).click();
    await expect(page).toHaveURL("/");
  });
});
