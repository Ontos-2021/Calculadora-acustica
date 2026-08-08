import { test, expect } from "@playwright/test";

test.describe("Error states", () => {
  test("shows error when no data query param", async ({ page }) => {
    await page.goto("/results");
    await expect(page.getByText("No se encontraron datos de cálculo.")).toBeVisible({ timeout: 10000 });
  });

  test("shows error on corrupt base64", async ({ page }) => {
    // atob() throws DOMException; caught and rendered
    await page.goto("/results?data=not-valid-base64!!!!");
    // The error text is the browser's atob error, not a custom message
    // Use the error container (red bg) as indicator
    const errorBox = page.locator(".bg-red-50");
    await expect(errorBox).toBeVisible({ timeout: 5000 });
    // Volver link should be present
    await expect(page.getByRole("link", { name: "Volver" })).toBeVisible();
  });

  test("handles invalid encoded JSON gracefully", async ({ page }) => {
    const encoded = btoa("not-json");
    await page.goto(`/results?data=${encoded}`);
    // JSON.parse throws, caught and rendered
    const errorBox = page.locator(".bg-red-50");
    await expect(errorBox).toBeVisible({ timeout: 5000 });
    await expect(page.getByRole("link", { name: "Volver" })).toBeVisible();
  });

  test("shows error when backend is unreachable", async ({ page }) => {
    await page.route("**/api/v1/**", (route) => route.abort("connectionrefused"));
    const encoded = btoa(JSON.stringify({ largo: 5, ancho: 4, alto: 3, superficies: [{ material: "Concreto" }] }));
    await page.goto(`/results?data=${encoded}`);
    const errorBox = page.locator(".bg-red-50");
    await expect(errorBox).toBeVisible({ timeout: 5000 });
    await expect(page.getByRole("link", { name: "Volver" })).toBeVisible();
  });

  test("Volver button navigates to home from error", async ({ page }) => {
    await page.goto("/results");
    await page.getByRole("link", { name: "Volver" }).click();
    await expect(page).toHaveURL("/");
  });
});
