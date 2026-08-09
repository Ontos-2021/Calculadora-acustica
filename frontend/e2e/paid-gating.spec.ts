import { test, expect } from "./fixtures/test";
import { activatePaidLicense, API_URL, gotoResults, PAID_KEY } from "./fixtures/helpers";
import { SALA_BASE } from "./fixtures/payloads";

test.describe("Licencia y autorización", () => {
  test("una cadena cualquiera no desbloquea herramientas", async ({ page }) => {
    test.info().annotations.push({ type: "expected-console-error", description: "status of 401" });
    await gotoResults(page, SALA_BASE);
    await page.locator("#license-key").fill("not-a-license");
    await page.getByRole("button", { name: "Activar" }).click();
    const license = page.getByRole("region", { name: "Licencia y clave API" });
    await expect(license.getByRole("alert")).toContainText("clave API no es válida");
    await page.getByRole("tab", { name: "Diseño" }).click();
    await expect(page.getByText(/Activa una licencia con la función inverse_design/)).toBeVisible();
  });

  test("valida PAID, persiste solo en sesión y revoca localmente", async ({ page }) => {
    await gotoResults(page, SALA_BASE);
    await activatePaidLicense(page);
    await page.reload();
    const license = page.getByRole("region", { name: "Licencia y clave API" });
    await expect(license.getByText("PAID", { exact: true })).toBeVisible({ timeout: 15_000 });
    await license.getByRole("button", { name: "Revocar sesión local" }).click();
    await expect(page.locator("#license-key")).toBeVisible();
    const stored = await page.evaluate(() => sessionStorage.getItem("acoustic-api-key"));
    expect(stored).toBeNull();
  });

  test("backend devuelve 401 sin clave y datos numéricos con clave válida", async ({ request }) => {
    const denied = await request.post(`${API_URL}/api/v1/design/absorbers/porous`, { data: { thickness_m: 0.05, flow_resistivity: 10000, density_kgm3: 100 } });
    expect(denied.status()).toBe(401);
    const allowed = await request.post(`${API_URL}/api/v1/design/absorbers/porous`, {
      headers: { "X-API-Key": PAID_KEY },
      data: { thickness_m: 0.05, flow_resistivity: 10000, density_kgm3: 100 },
    });
    expect(allowed.status()).toBe(200);
    const payload = await allowed.json();
    expect(payload.alpha[1000]).toBeGreaterThan(0);
    expect(payload.estimate_label).toContain("estimate");
  });

  test("errores 403 son claros para un entitlement ausente", async ({ page }) => {
    await gotoResults(page, SALA_BASE);
    await activatePaidLicense(page);
    const response = await page.request.post(`${API_URL}/api/v1/numerical/fem2d/polygon`, {
      headers: { "X-API-Key": PAID_KEY },
      data: { vertices: [[0, 0], [2, 0], [2, 2], [0, 2]], target_edge_length_m: 0.5, num_modes: 2 },
    });
    expect(response.status()).toBe(403);
    expect((await response.json()).detail).toContain("research");
  });
});
