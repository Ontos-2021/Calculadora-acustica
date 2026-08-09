import { test, expect } from "./fixtures/test";
import { activatePaidLicense, gotoResults, openTab, RESEARCH_KEY } from "./fixtures/helpers";
import { SALA_BASE } from "./fixtures/payloads";

test.describe("Métodos numéricos", () => {
  test("impedancia finita usa dimensiones y ambiente actuales", async ({ page }) => {
    await gotoResults(page, SALA_BASE); await activatePaidLicense(page); await openTab(page, "Avanzado");
    await expect(page.getByText("Geometría actual:")).toContainText("8.5 × 6 × 3 m");
    await page.locator("#num-imp-z").fill("5000");
    await page.getByRole("button", { name: "Ejecutar con la sala actual" }).click();
    const result = page.getByText("Resultado numérico y estado de investigación").locator("..");
    await result.getByText("Ver datos y diagnósticos completos").click();
    const payload = JSON.parse(await result.locator("pre").textContent() || "{}");
    expect(payload.environment.temperature_c).toBe(20);
    expect(payload.axial_modes[0].frequency_hz).toBeGreaterThan(0);
  });

  test("FEM 2D devuelve modos y residuales", async ({ page }) => {
    await gotoResults(page, SALA_BASE); await activatePaidLicense(page); await openTab(page, "Avanzado");
    await page.getByRole("tab", { name: "FEM 2D", exact: true }).click();
    await page.locator("#num-fem-nx").fill("12");
    await page.locator("#num-fem-ny").fill("12");
    await page.locator("#num-fem-modos").fill("3");
    await page.getByRole("button", { name: "Ejecutar con la sala actual" }).click();
    const result = page.getByText("Resultado numérico y estado de investigación").locator("..");
    await result.getByText("Ver datos y diagnósticos completos").click();
    const payload = JSON.parse(await result.locator("pre").textContent() || "{}");
    expect(payload.modes.length).toBe(3);
    expect(payload.modes[0].residual).toBeLessThan(0.1);
  });

  test("licencia RESEARCH ejecuta FEM poligonal", async ({ page }) => {
    await gotoResults(page, SALA_BASE); await activatePaidLicense(page, RESEARCH_KEY, "RESEARCH"); await openTab(page, "Avanzado");
    await page.getByRole("tab", { name: "FEM polígono" }).click();
    await page.locator("#num-fem-modos").fill("3");
    await page.getByRole("button", { name: "Ejecutar con la sala actual" }).click();
    const result = page.getByText("Resultado numérico y estado de investigación").locator("..");
    await result.getByText("Ver datos y diagnósticos completos").click();
    const payload = JSON.parse(await result.locator("pre").textContent() || "{}");
    expect(payload.nodes.length).toBeGreaterThan(20);
    expect(payload.modes.length).toBe(3);
    expect(payload.research_status).toContain("Research");
  });
});
