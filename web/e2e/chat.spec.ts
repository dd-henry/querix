import { expect, test, type Page } from "@playwright/test";

const approvedProfile = {
  id: "user-1",
  email: "user@example.com",
  name: "User",
  role: "user",
  status: "approved",
};

const reviewResponse = {
  conversation_id: "conversation-1",
  request_id: "request-1",
  status: "review",
  content: "SQL gerado para revisão.",
  sql: "SELECT label, total FROM sales",
  chart: {
    tipo: "bar",
    eixo_x: "label",
    eixo_y: "total",
    titulo: "Vendas",
  },
  retryable: false,
  warnings: [],
};

async function mockAuthenticatedPage(page: Page) {
  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(approvedProfile),
    });
  });
  await page.route("**/api/conversations*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ groups: [], expired_count: 0 }),
    });
  });
}

async function openChat(page: Page) {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Converse com seus dados" }),
  ).toBeVisible();
}

test("keeps one user and assistant message during a double-clicked send", async ({
  page,
}) => {
  await mockAuthenticatedPage(page);
  let releaseTranslation!: () => void;
  const translation = new Promise<void>((resolve) => {
    releaseTranslation = resolve;
  });
  let translateCalls = 0;
  await page.route("**/api/chat/translate", async (route) => {
    translateCalls += 1;
    await translation;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(reviewResponse),
    });
  });

  await openChat(page);
  await page.getByLabel("Pergunte sobre seus dados").fill("Total de vendas");
  await page.getByRole("button", { name: "Enviar pergunta" }).dblclick();

  await expect(page.locator("[data-message-id$=':user']")).toHaveCount(1);
  await expect(page.locator("[data-message-id$=':assistant']")).toHaveCount(1);
  await expect(page.locator("textarea")).toHaveCount(1);
  await expect(page.locator(".chat-message__pending")).toHaveCount(1);
  expect(translateCalls).toBe(1);

  releaseTranslation();
  await expect(page.getByText("SQL gerado para revisão.")).toBeVisible();
});

test("executes reviewed SQL once, keeps controls stable, and exposes chart and CSV", async ({
  page,
}) => {
  await mockAuthenticatedPage(page);
  await page.route("**/api/chat/translate", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(reviewResponse),
    });
  });
  let releaseExecution!: () => void;
  const execution = new Promise<void>((resolve) => {
    releaseExecution = resolve;
  });
  let executeCalls = 0;
  await page.route("**/api/chat/execute", async (route) => {
    executeCalls += 1;
    await execution;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ...reviewResponse,
        status: "executed",
        content: "Aqui estão os resultados da consulta:",
        result: {
          columns: ["label", "total"],
          rows: [{ label: "Janeiro", total: 12 }],
          row_count: 1,
          truncated: false,
        },
      }),
    });
  });

  await openChat(page);
  await page.getByLabel("Pergunte sobre seus dados").fill("Total de vendas");
  await page.getByRole("button", { name: "Enviar pergunta" }).click();
  await page.getByRole("button", { name: "Executar SQL revisado" }).click();

  await expect(page.getByLabel("Pergunte sobre seus dados")).toBeDisabled();
  await expect(page.locator("[data-message-id$=':user']")).toHaveCount(1);
  await expect(page.locator("[data-message-id$=':assistant']")).toHaveCount(1);
  expect(executeCalls).toBe(1);

  releaseExecution();
  await expect(
    page.getByRole("heading", { name: "Resultados" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Gerar Gráfico" }).click();
  await expect(page.getByTestId("bar-chart")).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download Relatório (CSV)" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^relatorio-.*\.csv$/);
});

test("retries the same failed request and keeps warning responses non-executable", async ({
  page,
}) => {
  await mockAuthenticatedPage(page);
  let translateCalls = 0;
  let executeCalls = 0;
  await page.route("**/api/chat/translate", async (route) => {
    translateCalls += 1;
    if (translateCalls === 1) {
      await route.fulfill({
        status: 502,
        contentType: "application/json",
        body: JSON.stringify({
          error: {
            code: "translator_unavailable",
            message: "Translator unavailable.",
          },
        }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ...reviewResponse,
        status: "warning",
        content: "AVISO: tabela não encontrada.",
        sql: null,
        chart: null,
      }),
    });
  });
  await page.route("**/api/chat/retry", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(reviewResponse),
    });
  });
  await page.route("**/api/chat/execute", async (route) => {
    executeCalls += 1;
    await route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({
        error: {
          code: "unexpected",
          message: "Execution should not be called.",
        },
      }),
    });
  });

  await openChat(page);
  await page.getByLabel("Pergunte sobre seus dados").fill("Total de vendas");
  await page.getByRole("button", { name: "Enviar pergunta" }).click();
  await expect(page.getByText("Translator unavailable.")).toBeVisible();
  await page.getByRole("button", { name: "Tentar novamente" }).click();
  await expect(page.getByText("SQL gerado para revisão.")).toBeVisible();
  await expect(page.locator("[data-message-id$=':user']")).toHaveCount(1);
  await expect(page.locator("[data-message-id$=':assistant']")).toHaveCount(1);

  await page.getByRole("button", { name: "Cancelar revisão" }).click();
  await page.getByLabel("Pergunte sobre seus dados").fill("Outra pergunta");
  await page.getByRole("button", { name: "Enviar pergunta" }).click();

  await expect(page.getByText("AVISO: tabela não encontrada.")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Executar SQL revisado" }),
  ).toHaveCount(0);
  expect(executeCalls).toBe(0);
});
