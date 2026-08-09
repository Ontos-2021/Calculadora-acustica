import { readFile } from "node:fs/promises";
import { PDFParse } from "pdf-parse";
import { test, expect } from "./fixtures/test";
import { activatePaidLicense, gotoResults } from "./fixtures/helpers";
import { SALA_CON_USO } from "./fixtures/payloads";

test.describe("Exportación profesional", () => {
  test.beforeEach(async ({ page }) => { await gotoResults(page, SALA_CON_USO); await activatePaidLicense(page); });

  test("JSON conserva esquema, entrada y resultados completos", async ({ page }) => {
    await page.getByRole("tab", { name: "Presión" }).click();
    await expect(page.getByText("Magnitud RMS modal ponderada normalizada")).toBeVisible({ timeout: 20_000 });
    const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "JSON completo" }).click()]);
    const payload = JSON.parse(await readFile((await download.path())!, "utf8"));
    expect(payload.schema_version).toBe("acoustic-report/2.0");
    expect(payload.input.superficies).toHaveLength(6);
    expect(payload.input.environment.temperature_c).toBe(20);
    expect(payload.results.rt60_bandas[500].Sabine).toBeGreaterThan(0);
    expect(payload.results.modos.length).toBeGreaterThan(10);
    expect(payload.pressure.optimal_listening.movement_m).toBeGreaterThanOrEqual(0);
    expect(payload.certification).toContain("not_measurement_or_certification");
  });

  test("CSV incluye metadata, materiales, RT, modos y presión", async ({ page }) => {
    await page.getByRole("tab", { name: "Presión" }).click();
    await expect(page.getByText("Magnitud RMS modal ponderada normalizada")).toBeVisible({ timeout: 20_000 });
    const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "CSV completo" }).click()]);
    const csv = await readFile((await download.path())!, "utf8");
    expect(csv).toContain("acoustic-report/2.0");
    expect(csv).toContain('"input","surface_0","material","Concreto"');
    expect(csv).toContain('"rt60","500_hz","Sabine"');
    expect(csv).toContain('"mode","1","frequency"');
    expect(csv).toContain('"pressure","recommendation","improvement"');
  });

  test("LaTeX y Typst contienen procedencia y no certificación", async ({ page }) => {
    const [latexDownload] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "LaTeX" }).click()]);
    const latex = await readFile((await latexDownload.path())!, "utf8");
    expect(latex).toContain("\\documentclass");
    expect(latex).toContain("No certificación");
    expect(latex).toContain("acoustic\\_core del servidor");
    const [typstDownload] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Typst" }).click()]);
    const typst = await readFile((await typstDownload.path())!, "utf8");
    expect(typst).toContain("Informe acústico profesional");
    expect(typst).toContain("No certificación");
    expect(typst).toContain("RT60 modelado");
  });

  test("PDF se descarga y su texto incluye entrada, advertencia y procedencia", async ({ page }) => {
    const link = page.locator('a[download="informe-acustico-profesional.pdf"]');
    await expect(link).toBeVisible({ timeout: 20_000 });
    await expect(link).toHaveText("Descargar PDF", { timeout: 20_000 });
    const [download] = await Promise.all([page.waitForEvent("download"), link.click()]);
    const parser = new PDFParse({ data: await readFile((await download.path())!) });
    try {
      const parsed = await parser.getText();
      expect(parsed.text).toContain("Informe Acústico Profesional");
      expect(parsed.text).toContain("Entrada de sala y ambiente");
      expect(parsed.text).toMatch(/no es una medición/i);
      expect(parsed.text).toContain("acoustic_core del servidor");
      expect(parsed.text).toContain("RT60 por banda");
    } finally {
      await parser.destroy();
    }
  });
});
