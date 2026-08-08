import { Page } from "@playwright/test";

export async function gotoResults(page: Page, payload: Record<string, unknown>, timeout = 30000) {
  const encoded = btoa(JSON.stringify(payload));
  await page.goto(`/results?data=${encoded}`);
  // Wait for either results to render or error to appear
  await page.waitForLoadState("domcontentloaded");
  try {
    await page.getByText("RT60 Promedio").waitFor({ state: "visible", timeout });
  } catch {
    // If results didn't load, wait for error text instead
    await page.getByText("Error").or(page.getByText("No se encontraron")).waitFor({ state: "visible", timeout: 5000 });
  }
}

export async function fillRoom(page: Page, dims: { largo?: string; ancho?: string; alto?: string }) {
  if (dims.largo) await page.locator("#dim-largo").fill(dims.largo);
  if (dims.ancho) await page.locator("#dim-ancho").fill(dims.ancho);
  if (dims.alto) await page.locator("#dim-alto").fill(dims.alto);
}

export async function openTab(page: Page, label: string) {
  await page.getByRole("button", { name: new RegExp("^" + label + "(\\s|$)") }).click();
}
