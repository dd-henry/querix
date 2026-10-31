import { expect, test } from "@playwright/test";

test("loads the web shell", async ({ page }) => {
  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({
        error: {
          code: "auth_required",
          message: "Authentication required.",
        },
      }),
    });
  });
  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: "Entrar para continuar" }),
  ).toBeVisible();
});
