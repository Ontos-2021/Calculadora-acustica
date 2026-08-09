import { test as base, expect } from "@playwright/test";

export const test = base.extend<{ unexpectedBrowserErrors: void }>({
  unexpectedBrowserErrors: [async ({ page }, use, testInfo) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(`pageerror: ${error.message}`));
    page.on("console", (message) => {
      if (message.type() === "error") errors.push(`console: ${message.text()}`);
    });
    await use();
    const expected = testInfo.annotations
      .filter((annotation) => annotation.type === "expected-console-error")
      .map((annotation) => annotation.description || "");
    const unexpected = errors.filter((error) => !expected.some((pattern) => error.includes(pattern)));
    expect(unexpected, "unexpected browser errors").toEqual([]);
  }, { auto: true }],
});

export { expect } from "@playwright/test";
