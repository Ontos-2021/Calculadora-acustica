import { test, expect } from "./fixtures/test";
import { encodePayload } from "./fixtures/helpers";
import { SALA_BASE } from "./fixtures/payloads";

test.describe("Errores y recuperación", () => {
  test("explica datos ausentes o base64url malformado", async ({ page }) => {
    await page.goto("/results");
    await expect(page.getByRole("heading", { name: "Entiende la respuesta acústica de tu sala antes de construir." })).toBeVisible();
    await expect(page.locator("#dim-largo")).toBeVisible();
    await page.goto("/results?data=not-valid!!!!");
    await expect(page.getByRole("heading", { name: "Entiende la respuesta acústica de tu sala antes de construir." })).toBeVisible();
    await expect(page.locator("#dim-largo")).toBeVisible();
  });

  test("muestra validación 422 y no la disfraza como fallo offline", async ({ page }) => {
    test.info().annotations.push({ type: "expected-console-error", description: "status of 422" });
    await page.goto(`/results?data=${encodePayload({ ...SALA_BASE, largo: 2000 })}`);
    await expect(page.locator("main [role='alert']")).toContainText(/Revisa los datos ingresados|less than or equal/i);
    await expect(page.getByTestId("engine-source")).toHaveCount(0);
  });

  test("un fallo de red invoca el motor FREE real", async ({ page }) => {
    test.info().annotations.push({ type: "expected-console-error", description: "ERR_CONNECTION_REFUSED" });
    await page.route("**/api/v1/calculate", (route) => route.abort("connectionrefused"));
    await page.route("**/api/v1/pressure-map", (route) => route.abort("connectionrefused"));
    await page.goto(`/results?data=${encodePayload(SALA_BASE)}`);
    await expect(page.getByText("RT60 Promedio")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("engine-source")).toContainText("Estimación local");
    await expect(page.getByText(/Se conserva el resultado local/)).toBeVisible();
    const modeCount = Number(await page.getByText("Modos totales").locator("..").locator("p").nth(1).textContent());
    expect(modeCount).toBeGreaterThan(0);
  });

  test("permite iniciar una sala desde el workspace persistente", async ({ page }) => {
    await page.goto("/results");
    await expect(page.locator("#dim-largo")).toBeVisible();
    await page.locator("#dim-largo").fill("5");
    await page.locator("#dim-ancho").fill("4");
    await page.locator("#dim-alto").fill("3");
    await expect(page.locator("#env-temperature")).toHaveValue("20");
  });
});
