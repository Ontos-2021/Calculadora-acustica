import { test, expect } from "./fixtures/test";
import { decodePayload, fillRoom, gotoResults } from "./fixtures/helpers";
import { SALA_BASE } from "./fixtures/payloads";

test.describe("Flujo de cálculo anónimo", () => {
  test("envía el formulario y produce resultados numéricos", async ({ page }) => {
    await page.goto("/");
    await fillRoom(page, { largo: "8.5", ancho: "6", alto: "3" });
    await page.locator("#env-temperature").fill("24");
    await page.locator("#env-humidity").fill("60");
    await page.getByRole("button", { name: "Calcular" }).click();
    await expect(page).toHaveURL(/\/results\?data=/);
    await expect(page.getByText("RT60 Promedio")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("engine-source")).toContainText("Verificado por servidor", { timeout: 20_000 });
    await page.getByText("Supuestos, incertidumbre y procedencia").click();
    await expect(page.getByText("24.0 °C · 60 % HR")).toBeVisible();
    const value = parseFloat(await page.getByText("RT60 Promedio").locator("..").locator("p").nth(1).textContent() || "0");
    expect(value).toBeGreaterThan(0);
  });

  test("usa base64url Unicode seguro sin padding", async ({ page }) => {
    await page.goto("/");
    await fillRoom(page, { largo: "5", ancho: "4", alto: "3" });
    await page.getByRole("button", { name: "Calcular" }).click();
    await expect(page).toHaveURL(/\/results\?data=/);
    const encoded = new URL(page.url()).searchParams.get("data");
    expect(encoded).toBeTruthy();
    expect(encoded).not.toMatch(/[+/=]/);
    const decoded = decodePayload(encoded!);
    expect(decoded).toMatchObject({ largo: 5, ancho: 4, alto: 3 });
    expect(decoded.environment).toEqual({ temperature_c: 20, relative_humidity: 50, pressure_pa: 101325 });
  });

  test("integra velocidad del sonido, campo difuso y Bolt", async ({ page }) => {
    await gotoResults(page, SALA_BASE);
    await page.getByText("Supuestos, incertidumbre y procedencia").click();
    await expect(page.getByText("Velocidad", { exact: true })).toBeVisible();
    await expect(page.getByText("Campo difuso", { exact: true })).toBeVisible();
    await expect(page.getByText("Área de Bolt")).toBeVisible();
    const speed = await page.getByText("Velocidad", { exact: true }).locator("..").locator("dd").textContent();
    expect(Number(speed?.split(" ")[0])).toBeGreaterThan(330);
  });
});
