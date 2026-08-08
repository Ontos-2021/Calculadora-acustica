import { test, expect } from "@playwright/test";
import { gotoResults } from "./fixtures/helpers";
import { SALA_BASE } from "./fixtures/payloads";

test.describe("PAID feature gating", () => {
  test("ISM section shows gate with no API key", async ({ page }) => {
    await gotoResults(page, SALA_BASE);
    await expect(page.getByText("Esta funcionalidad requiere una licencia PAID.")).toBeVisible();
  });

  test("typing any API key reveals ISM form", async ({ page }) => {
    await gotoResults(page, SALA_BASE);
    await page.locator("#ism-apikey").fill("test-key");
    await expect(page.getByText("Esta funcionalidad requiere una licencia PAID.")).not.toBeVisible();
    await expect(page.getByText("Fuente X")).toBeVisible();
  });

  test("ISM endpoint returns 403 with any key", async ({ page }) => {
    // BUG: api/dependencies.py FEATURE_MAP requires 'ism' feature,
    // but no tier in TIERS grants it, so even valid keys get 403.
    await gotoResults(page, SALA_BASE);
    await page.locator("#ism-apikey").fill("free_tier");
    const responsePromise = page.waitForResponse(
      (r) => r.url().includes("/impulse-response") && r.request().method() === "POST"
    );
    await page.locator("#ism-fuente-x").fill("2");
    await page.locator("#ism-fuente-y").fill("1.5");
    await page.locator("#ism-fuente-z").fill("1.5");
    await page.locator("#ism-receptor-x").fill("4");
    await page.locator("#ism-receptor-y").fill("3");
    await page.locator("#ism-receptor-z").fill("1.2");
    await page.getByRole("button", { name: "Calcular respuesta al impulso" }).click();
    const response = await responsePromise;
    expect(response.status()).toBe(403);
    const body = await response.json();
    expect(body.detail).toContain("Requiere licencia PAID");
  });

  test("PAID calculator endpoints respond 200 without API key", async ({ page }) => {
    // BUG: Only /impulse-response enforces gating. All other PAID endpoints are public.
    let res = await page.request.post("http://localhost:8000/api/v1/design/absorbers/porous", {
      data: { thickness_m: 0.05, flow_resistivity: 10000, density_kgm3: 100 },
    });
    expect(res.status()).toBe(200);

    res = await page.request.post("http://localhost:8000/api/v1/design/isolation/single-panel", {
      data: { mass_per_area_kgm2: 50, thickness_m: 0.1 },
    });
    expect(res.status()).toBe(200);

    res = await page.request.post("http://localhost:8000/api/v1/measurement/ess", {
      data: { f1_hz: 20, f2_hz: 20000, duration_s: 1, sample_rate: 44100 },
    });
    expect(res.status()).toBe(200);
  });
});
