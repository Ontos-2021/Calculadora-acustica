import { test, expect } from "./fixtures/test";
import { activatePaidLicense, gotoResults, openTab } from "./fixtures/helpers";
import { SALA_BASE } from "./fixtures/payloads";

test.describe("Medición PAID", () => {
  test.beforeEach(async ({ page }) => { await gotoResults(page, SALA_BASE); await activatePaidLicense(page); await openTab(page, "Medición"); });

  test("genera ESS con cantidad de muestras comprobable", async ({ page }) => {
    await page.locator("#med-ess-f1").fill("30");
    await page.locator("#med-ess-f2").fill("18000");
    await page.locator("#med-ess-duracion").fill("0.1");
    await page.getByRole("button", { name: "Generar vista previa ESS" }).click();
    const result = page.getByText("Resultado de medición y diagnósticos").locator("..");
    await result.getByText("Ver datos y diagnósticos completos").click();
    const payload = JSON.parse(await result.locator("pre").textContent() || "{}");
    expect(payload.total_samples).toBe(4410);
    expect(payload.signal.length).toBeGreaterThan(100);
  });

  test("descarga un ESS WAV real e importa sus metadatos", async ({ page }) => {
    await page.locator("#med-ess-duracion").fill("0.1");
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: "Descargar ESS WAV" }).click(),
    ]);
    expect(download.suggestedFilename()).toMatch(/\.wav$/);
    const path = await download.path();
    expect(path).toBeTruthy();
    await page.getByRole("tab", { name: "Importar WAV" }).click();
    await page.locator("#med-wav-file").setInputFiles(path!);
    await page.getByRole("button", { name: "Importar metadatos y muestras" }).click();
    const result = page.getByText("Resultado de medición y diagnósticos").locator("..");
    await result.getByText("Ver datos y diagnósticos completos").click();
    const payload = JSON.parse(await result.locator("pre").textContent() || "{}");
    expect(payload.sample_rate).toBe(44100);
    expect(payload.num_frames).toBe(4410);
  });

  test("calcula espectrograma y Q modal desde una señal determinista", async ({ page }) => {
    await page.getByRole("tab", { name: "Señal" }).click();
    await page.locator("#med-signal-tool").selectOption("spectrogram");
    await page.getByRole("button", { name: "Analizar señal" }).click();
    let result = page.getByText("Resultado de medición y diagnósticos").locator("..");
    await result.getByText("Ver datos y diagnósticos completos").click();
    await expect(result.locator("pre")).toContainText("magnitude_db");
    await page.locator("#med-signal-tool").selectOption("modal-q");
    await page.getByRole("button", { name: "Analizar señal" }).click();
    result = page.getByText("Resultado de medición y diagnósticos").locator("..");
    await result.getByText("Ver datos y diagnósticos completos").click();
    const payload = JSON.parse(await result.locator("pre").textContent() || "{}");
    expect(payload.Q).toBeGreaterThan(0);
  });

  test("calibra las superficies de la sala actual y expone convergencia", async ({ page }) => {
    await page.getByRole("tab", { name: "Calibración" }).click();
    await page.locator("#med-cal-rt60").fill("0.7");
    await page.getByRole("button", { name: "Calibrar sala actual" }).click();
    const result = page.getByText("Resultado de medición y diagnósticos").locator("..");
    await result.getByText("Ver datos y diagnósticos completos").click();
    await expect(result.locator("pre")).toContainText("diagnostics");
    await expect(result.locator("pre")).toContainText("objective_history");
  });
});
