import { test, expect } from "./fixtures/test";
import { gotoResults } from "./fixtures/helpers";
import { SALA_BASE } from "./fixtures/payloads";

test.describe("Instalación offline FREE", () => {
  test("calienta la instalación, recarga resultados sin red y calcula datos reales", async ({ page, context }) => {
    test.info().annotations.push({ type: "expected-console-error", description: "ERR_INTERNET_DISCONNECTED" });
    await page.goto("/");
    await expect(page.locator("[data-offline-ready='true']")).toBeVisible({ timeout: 20_000 });
    await gotoResults(page, SALA_BASE);
    const resultsUrl = page.url();
    await context.setOffline(true);
    await page.goto(resultsUrl, { waitUntil: "domcontentloaded" });
    await expect(page.getByText("RT60 Promedio")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("engine-source")).toContainText("Motor FREE TypeScript determinista");
    const rtText = await page.getByText("RT60 Promedio").locator("..").locator("p").nth(1).textContent();
    expect(parseFloat(rtText || "0")).toBeGreaterThan(0);
    await page.getByRole("tab", { name: "Presión" }).click();
    await expect(page.getByText("Magnitud RMS modal ponderada normalizada")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText("Recomendación de escucha basada en uniformidad espectral")).toBeVisible();
  });

  test("service worker evita cachear métodos no GET y versiona los cachés", async ({ request }) => {
    const source = await (await request.get("/sw.js")).text();
    expect(source).toContain('request.method !== "GET"');
    expect(source).toContain("CACHE_PREFIX");
    expect(source).toContain("caches.delete");
    expect(source).toContain("/results.html");
    expect(source).not.toContain("core-bundle");
  });
});
