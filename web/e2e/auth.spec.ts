import { expect, test, type Page } from "@playwright/test";

const approvedProfile = {
  id: "user-1",
  email: "user@example.com",
  name: "User",
  role: "user",
  status: "approved",
};

async function mockUnauthenticated(page: Page) {
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
}

test("keeps one auth form while login is pending and shows one shell after success", async ({
  page,
}) => {
  await mockUnauthenticated(page);

  let releaseLogin!: () => void;
  const loginResponse = new Promise<void>((resolve) => {
    releaseLogin = resolve;
  });
  await page.route("**/api/auth/login", async (route) => {
    await loginResponse;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(approvedProfile),
    });
  });

  await page.goto("/");
  await expect(page.getByRole("tab", { name: "Entrar" })).toBeVisible();
  await page.getByLabel("Email").fill("user@example.com");
  await page.getByLabel("Senha").fill("password");

  const preSubmitInputCount = await page.locator("form input").count();
  const loginButton = page
    .locator("form")
    .getByRole("button", { name: "Entrar", exact: true });
  await loginButton.click();

  await expect(
    page.getByRole("button", { name: "Entrando...", exact: true }),
  ).toBeDisabled();
  await expect.poll(() => page.locator("form input").count()).toBe(
    preSubmitInputCount,
  );
  expect(await page.locator("form").count()).toBe(1);

  releaseLogin();
  await expect(
    page.getByRole("heading", { name: "Converse com seus dados" }),
  ).toHaveCount(1);
  await expect(page.locator("main")).toHaveCount(1);
  await expect(page.locator("aside")).toHaveCount(1);
  await expect(page.locator("form")).toHaveCount(0);
});

test("keeps one form and clears only the password after an invalid login", async ({
  page,
}) => {
  await mockUnauthenticated(page);
  await page.route("**/api/auth/login", async (route) => {
    await route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({
        error: {
          code: "auth_failed",
          message: "Email ou senha inválidos.",
        },
      }),
    });
  });

  await page.goto("/");
  await page.getByLabel("Email").fill("user@example.com");
  await page.getByLabel("Senha").fill("wrong-password");
  await page
    .locator("form")
    .getByRole("button", { name: "Entrar", exact: true })
    .click();

  await expect(page.getByRole("alert")).toHaveText(
    "Não foi possível entrar: Email ou senha inválidos.",
  );
  await expect(page.locator("form")).toHaveCount(1);
  await expect(page.locator("input")).toHaveCount(2);
  await expect(page.getByLabel("Email")).toHaveValue("user@example.com");
  await expect(page.getByLabel("Senha")).toHaveValue("");
});

test("blocks invalid signup data before making an API request", async ({
  page,
}) => {
  await mockUnauthenticated(page);
  let signupCalled = false;
  await page.route("**/api/auth/signup", async (route) => {
    signupCalled = true;
    await route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({
        error: {
          code: "unexpected",
          message: "Should not be called.",
        },
      }),
    });
  });

  await page.goto("/");
  await page.getByRole("tab", { name: "Criar conta" }).click();
  await page.getByLabel("Nome completo").fill("New User");
  await page.getByLabel("Email").fill("new@example.com");
  await page.getByLabel("Senha", { exact: true }).fill("short");
  await page.getByLabel("Confirmar senha").fill("short");
  await page.getByRole("button", { name: "Solicitar acesso" }).click();

  await expect(page.getByRole("alert")).toHaveText(
    "A senha deve ter pelo menos 8 caracteres.",
  );
  expect(signupCalled).toBe(false);
});

test("returns to one login screen after logout", async ({ page }) => {
  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(approvedProfile),
    });
  });
  await page.route("**/api/auth/logout", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ message: "Logged out." }),
    });
  });

  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Converse com seus dados" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Sair", exact: true }).click();

  await expect(
    page.getByRole("heading", { name: "Entrar para continuar" }),
  ).toHaveCount(1);
  await expect(page.locator("form")).toHaveCount(1);
  await expect(page.locator("input")).toHaveCount(2);
});
