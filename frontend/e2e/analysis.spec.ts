import { test, expect } from "./fixtures/test";
import { gotoResults, openTab } from "./fixtures/helpers";
import { SALA_BASE } from "./fixtures/payloads";

test.describe("Análisis modal y RT60", () => {
  test.beforeEach(async ({ page }) => { await gotoResults(page, SALA_BASE); });

  test("muestra modos y valores RT60 a precisión sensata", async ({ page }) => {
    await openTab(page, "Modos");
    await expect(page.getByRole("heading", { name: /Modos de resonancia/ })).toBeVisible();
    expect(await page.locator("table tbody tr").count()).toBeGreaterThan(5);
    await openTab(page, "RT60");
    await expect(page.getByText("RT60 por Banda de Octava")).toBeVisible();
    const sabine = await page.locator("table").filter({ hasText: "Sabine" }).locator("tbody tr").first().locator("td").nth(1).textContent();
    expect(Number(sabine)).toBeGreaterThan(0);
  });

  test("filtra por tipo y frecuencia", async ({ page }) => {
    await openTab(page, "Modos");
    await page.locator("#modos-tipo").selectOption("axial");
    await page.locator("#modos-fmin").fill("80");
    await page.locator("#modos-fmax").fill("140");
    const rows = page.locator("table").filter({ hasText: "Frec (Hz)" }).locator("tbody tr");
    expect(await rows.count()).toBeGreaterThan(0);
    for (const text of await rows.locator("td:nth-child(6)").allTextContents()) expect(text).toContain("Ax");
  });

  test("una fila es operable por teclado y abre su contexto de presión", async ({ page }) => {
    await openTab(page, "Modos");
    const row = page.locator("table").filter({ hasText: "Frec (Hz)" }).locator("tbody tr").first();
    await row.focus();
    await row.press("Enter");
    await expect(page.getByRole("tab", { name: "Presión" })).toHaveAttribute("aria-selected", "true");
    await expect(page.locator("#presion-modo")).not.toHaveValue("all");
    await expect(page.getByText("Presión modal normalizada con signo")).toBeVisible({ timeout: 20_000 });
  });

  test("presenta Bonello, proporciones y advertencias metodológicas", async ({ page }) => {
    await openTab(page, "Modos");
    await expect(page.getByText("Criterio de Bonello")).toBeVisible();
    await expect(page.getByText("Proporciones de Sala")).toBeVisible();
    await openTab(page, "Resumen");
    await page.getByText("Supuestos, incertidumbre y procedencia").click();
    await expect(page.getByText(/Estimación de ingeniería para sala rectangular/)).toBeVisible();
    await expect(page.getByText(/avisos de aplicabilidad del método/)).toBeVisible();
  });
});
