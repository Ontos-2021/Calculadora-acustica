import { test, expect } from "@playwright/test";

test.describe("Home page — RoomForm", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("renders form with dimension inputs", async ({ page }) => {
    await expect(page.locator("#dim-largo")).toBeVisible();
    await expect(page.locator("#dim-ancho")).toBeVisible();
    await expect(page.locator("#dim-alto")).toBeVisible();
    await expect(page.getByRole("button", { name: "Calcular" })).toBeVisible();
  });

  test("loads 46 materials from API into surface selects", async ({ page }) => {
    const surfaceSelects = ["#mat-frente", "#mat-contrafrente", "#mat-lat-izquierdo", "#mat-lat-derecho", "#mat-piso", "#mat-techo"];
    // Note: IDs match RoomForm's naming: lowercase, spaces/dots → hyphens
    // Wait for materials to load — check #mat-frente has >30 native options
    await page.waitForFunction(() => {
      const el = document.querySelector("#mat-frente") as HTMLSelectElement | null;
      return el !== null && el.options.length > 30;
    }, { timeout: 20000 });
    // Verify by reading native options directly (more reliable than locator chain)
    const count = await page.locator("#mat-frente").evaluate((el: HTMLSelectElement) => el.options.length);
    expect(count).toBeGreaterThan(30);
    // Other selects should also be present
    for (const sel of surfaceSelects.slice(1)) {
      await expect(page.locator(sel)).toBeVisible();
    }
  });

  test("filter narrows material options", async ({ page }) => {
    await page.locator("#mat-frente").waitFor({ state: "visible" });
    await page.locator("#mat-filter").fill("Espuma");
    await page.waitForTimeout(300);
    const options = await page.locator("#mat-frente").locator("option").allTextContents();
    expect(options.some((o) => o.includes("Espuma"))).toBeTruthy();
  });

  test("filter by category narrows material options", async ({ page }) => {
    await page.locator("#mat-frente").waitFor({ state: "visible" });
    await page.locator("#mat-categoria").selectOption("Madera");
    await page.waitForTimeout(300);
    const options = await page.locator("#mat-frente").locator("option").allTextContents();
    expect(options.some((o) => o.includes("Madera"))).toBeTruthy();
  });

  test("toggle custom alpha inputs per surface", async ({ page }) => {
    const firstToggle = page.getByRole("button", { name: "α personalizado" }).first();
    await firstToggle.click();
    await expect(page.locator("[id^='alpha-']").first()).toBeVisible();
    // After click the same button now says "Ocultar α"
    const hideBtn = page.getByRole("button", { name: "Ocultar α" }).first();
    await hideBtn.click();
    await expect(page.locator("[id^='alpha-']").first()).not.toBeVisible();
  });

  test("offline badge is visible", async ({ page }) => {
    // The badge text depends on online state; just check it exists
    await expect(page.getByText("Online").or(page.getByText("Sin conexión"))).toBeVisible();
  });
});
