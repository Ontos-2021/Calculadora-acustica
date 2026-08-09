import type { Page } from "@playwright/test";

export const PAID_KEY = "ac_eeeeeeeeeeee_PlaywrightPaidKey_0123456789abcdefghijklmnop";
export const RESEARCH_KEY = "ac_dddddddddddd_PlaywrightResearchKey_0123456789abcdefghijklmn";
export const API_URL = process.env.E2E_API_URL || "http://127.0.0.1:8010";

export function encodePayload(payload: Record<string, unknown>): string {
  return Buffer.from(JSON.stringify(payload), "utf8").toString("base64url");
}

export function decodePayload(value: string): Record<string, unknown> {
  return JSON.parse(Buffer.from(value, "base64url").toString("utf8"));
}

export async function gotoResults(page: Page, payload: Record<string, unknown>, timeout = 30_000) {
  await page.goto(`/results?data=${encodePayload(payload)}`);
  await page.getByText("RT60 Promedio").waitFor({ state: "visible", timeout });
}

export async function activatePaidLicense(page: Page, key = PAID_KEY, tier: "PAID" | "RESEARCH" = "PAID") {
  const form = page.locator("#license-key");
  if (!(await form.count())) return;
  if (!(await form.first().isVisible().catch(() => false))) return;
  await form.first().fill(key);
  await page.getByRole("button", { name: "Activar" }).click();
  await page
    .getByRole("region", { name: "Licencia y clave API" })
    .getByText(tier, { exact: true })
    .waitFor({ state: "visible" });
}

export async function fillRoom(page: Page, dims: { largo?: string; ancho?: string; alto?: string }) {
  if (dims.largo) await page.locator("#dim-largo").fill(dims.largo);
  if (dims.ancho) await page.locator("#dim-ancho").fill(dims.ancho);
  if (dims.alto) await page.locator("#dim-alto").fill(dims.alto);
}

export async function openTab(page: Page, label: string) {
  await page.getByRole("tab", { name: new RegExp(`^${label}(\\s|$)`) }).first().click();
}
