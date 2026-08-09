import { test, expect } from "./fixtures/test";
import { activatePaidLicense, gotoResults, openTab } from "./fixtures/helpers";
import { SALA_CON_USO } from "./fixtures/payloads";

test.describe("Aislamiento PAID", () => {
  test.beforeEach(async ({ page }) => { await gotoResults(page, SALA_CON_USO); await activatePaidLicense(page); await openTab(page, "Aislamiento"); });

  test("panel simple devuelve tercio de octava, STC y Rw", async ({ page }) => {
    await page.locator("#aisl-simple-masa").fill("100");
    await page.locator("#aisl-simple-espesor").fill("0.12");
    await page.getByRole("tabpanel", { name: "Aislamiento", exact: true }).getByRole("button", { name: "Calcular", exact: true }).click();
    await expect(page.getByText("Pérdida por transmisión en tercio de octava")).toBeVisible({ timeout: 20_000 });
    const result = page.getByText("Resultado de aislamiento y supuestos").locator("..");
    await result.getByText("Ver datos y diagnósticos completos").click();
    await expect(result.locator("pre")).toContainText('"stc"');
    await expect(result.locator("pre")).toContainText('"rw"');
  });

  test("evalúa clasificación NR con una curva real", async ({ page }) => {
    await page.getByRole("tab", { name: "NC / NR" }).click();
    await page.getByRole("radio", { name: "NR", exact: true }).check();
    await page.getByRole("tabpanel", { name: "Aislamiento", exact: true }).getByRole("button", { name: "Calcular", exact: true }).click();
    const result = page.getByText("Resultado de aislamiento y supuestos").locator("..");
    await result.getByText("Ver datos y diagnósticos completos").click();
    await expect(result.locator("pre")).toContainText('"nr"');
    const payload = JSON.parse(await result.locator("pre").textContent() || "{}");
    expect(payload.nr).toBeGreaterThan(0);
  });

  test("calcula atenuación de conducto y flanqueo", async ({ page }) => {
    await page.getByRole("tab", { name: "Conducto" }).click();
    await page.getByRole("tabpanel", { name: "Aislamiento", exact: true }).getByRole("button", { name: "Calcular", exact: true }).click();
    let result = page.getByText("Resultado de aislamiento y supuestos").locator("..");
    await result.getByText("Ver datos y diagnósticos completos").click();
    await expect(result.locator("pre")).toContainText("insertion_loss_db");
    await page.getByRole("tab", { name: "Flancos" }).click();
    await page.getByRole("tabpanel", { name: "Aislamiento", exact: true }).getByRole("button", { name: "Calcular", exact: true }).click();
    result = page.getByText("Resultado de aislamiento y supuestos").locator("..");
    await result.getByText("Ver datos y diagnósticos completos").click();
    const payload = JSON.parse(await result.locator("pre").textContent() || "{}");
    expect(payload.apparent_tl_db).toBeLessThan(55);
  });
});
