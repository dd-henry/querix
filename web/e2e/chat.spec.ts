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
  await page.route("**/api/chat/status", (route) =>
    route.fulfill({
      json: {
        status: "running",
        phase: "executing",
        message: "A consulta está em andamento.",
        elapsed_seconds: 0,
      },
    }),
  );
}

async function openChat(page: Page) {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Converse com seus dados" }),
  ).toBeVisible();
}

for (const viewport of [
  { width: 1680, height: 900 },
  { width: 390, height: 844 },
]) {
  test(`keeps chat width stable for long SQL at ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await mockAuthenticatedPage(page);
    const sql = `SELECT ${"long_identifier".repeat(150)} FROM sales`;
    const summary = `${"Resumo da consulta. ".repeat(20)}Fim.`;
    await page.route("**/api/chat/translate", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ...reviewResponse,
          status: "executed",
          content: "Resultado da consulta.",
          sql,
          summary,
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
    const result = page.getByRole("region", { name: "Resultados da consulta" });
    await expect(result).toBeVisible();
    const panel = page.locator(".authenticated-panel");
    const table = result.getByRole("table");
    const measure = async () => ({
      panel: await panel.boundingBox(),
      result: await result.boundingBox(),
      table: await table.boundingBox(),
      documentWidth: await page.evaluate(() => document.documentElement.scrollWidth),
    });
    const before = await measure();
    await result.getByText("Ver SQL executado").click();
    await expect(result.locator("pre")).toHaveText(sql);
    const after = await measure();
    expect(before.panel).not.toBeNull();
    expect(after.panel!.width).toBeCloseTo(before.panel!.width, 1);
    expect(after.panel!.x).toBeCloseTo(before.panel!.x, 1);
    expect(after.result!.width).toBeCloseTo(before.result!.width, 1);
    expect(after.table!.width).toBeCloseTo(before.table!.width, 1);
    expect(after.documentWidth).toBeLessThanOrEqual(viewport.width);
    expect(await result.locator("pre").evaluate((el) => el.scrollHeight > el.clientHeight)).toBe(true);

    const expand = result.getByRole("button", { name: "Ler resumo completo" });
    await expect(expand).toHaveAttribute("aria-expanded", "false");
    await expect(expand).toHaveCSS("background-color", "rgb(51, 65, 85)");
    await expand.click();
    await expect(result.getByRole("button", { name: "Mostrar menos" })).toHaveAttribute("aria-expanded", "true");
    await expect(result).toContainText(summary);
  });
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
  let requestBody: Record<string, unknown> | undefined;
  await page.route("**/api/chat/translate", async (route) => {
    translateCalls += 1;
    requestBody = route.request().postDataJSON() as Record<string, unknown>;
    await translation;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ...reviewResponse,
        status: "executed",
        content: "Aqui estão os resultados da consulta:",
        summary: "O faturamento retornado foi R$ 12,00.",
        result: {
          columns: ["label", "total"],
          rows: [{ label: "Janeiro", total: 12 }],
          row_count: 1,
          truncated: false,
        },
        insights: [
          {
            key: "kpi",
            title: "Indicadores do período",
            summary: "A consulta retornou 1 linha(s).",
            sql: "SELECT COUNT(*) FROM sales",
            result: {
              columns: ["total"],
              rows: [{ total: 1 }],
              row_count: 1,
              truncated: false,
            },
          },
        ],
        interpretation: {
          intent: "Total de vendas por período",
          dimensions: ["label"],
          metrics: ["total"],
          period: {
            label: "mês atual",
            start: "2025-01-01",
            end: "2025-02-01",
          },
          assumptions: ["total representa a métrica disponível"],
        },
      }),
    });
  });

  await openChat(page);
  await page.getByLabel("Pergunte sobre seus dados").fill("Total de vendas");
  await page.getByRole("button", { name: "Enviar pergunta" }).dblclick();

  await expect(page.locator("[data-message-id$=':user']")).toHaveCount(1);
  await expect(page.locator("[data-message-id$=':assistant']")).toHaveCount(1);
  await expect(page.locator("textarea")).toHaveCount(1);
  await expect(page.locator(".chat-message__pending")).toHaveCount(1);
  await expect.poll(() => translateCalls).toBe(1);

  releaseTranslation();
  await expect(
    page.getByText("O faturamento retornado foi R$ 12,00."),
  ).toBeVisible();
  const insights = page.getByRole("region", { name: "Leitura gerencial" });
  const insightsDetails = insights.locator("details.chat-collapsible");
  await expect(insightsDetails).not.toHaveAttribute("open", "");
  await insights
    .getByRole("button", { name: /Leitura gerencial/ })
    .click();
  await expect(
    page.getByRole("heading", { name: "Indicadores do período" }),
  ).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Interpretação da pergunta" }),
  ).toContainText("Total de vendas por período");
  await expect(
    page.getByRole("region", { name: "Interpretação da pergunta" }),
  ).toContainText("mês atual");
  await expect(page.locator("[data-message-id$=':user']")).toHaveCount(1);
  await expect(page.locator("[data-message-id$=':assistant']")).toHaveCount(1);
  expect(requestBody?.review_mode).toBe(false);
  await expect(
    page.getByRole("button", { name: "Executar SQL revisado" }),
  ).toHaveCount(0);
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
        summary: "O faturamento retornado foi R$ 12,00.",
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
  await expect.poll(() => executeCalls).toBe(1);

  releaseExecution();
  await expect(
    page.getByRole("heading", { name: "Resultados" }),
  ).toBeVisible();
  await expect(
    page.getByText("O faturamento retornado foi R$ 12,00."),
  ).toBeVisible();
  await page.getByText("Ver SQL executado").click();
  await expect(page.getByText("SELECT label, total FROM sales")).toBeVisible();
  await page.getByRole("button", { name: "Gerar Gráfico" }).click();
  await expect(page.getByTestId("bar-chart")).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download Relatório (CSV)" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^relatorio-.*\.csv$/);
});

test("keeps the primary answer visible when a managerial insight fails", async ({
  page,
}) => {
  await mockAuthenticatedPage(page);
  await page.route("**/api/chat/translate", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ...reviewResponse,
        status: "executed",
        content: "Aqui estão os resultados da consulta:",
        summary: "O faturamento retornado foi R$ 12,00.",
        result: {
          columns: ["label", "total"],
          rows: [{ label: "Janeiro", total: 12 }],
          row_count: 1,
          truncated: false,
        },
        insights: [
          {
            key: "payments",
            title: "Formas de pagamento",
            warning: "Não foi possível calcular esta análise complementar.",
          },
        ],
      }),
    });
  });

  await openChat(page);
  await page.getByLabel("Pergunte sobre seus dados").fill("Total de vendas");
  await page.getByRole("button", { name: "Enviar pergunta" }).click();

  await expect(page.getByRole("heading", { name: "Resultados" })).toBeVisible();
  const insights = page.getByRole("region", { name: "Leitura gerencial" });
  const insightsDetails = insights.locator("details.chat-collapsible");
  await expect(insightsDetails).not.toHaveAttribute("open", "");
  await insights
    .getByRole("button", { name: /Leitura gerencial/ })
    .click();
  await expect(
    page.getByText("Não foi possível calcular esta análise complementar."),
  ).toBeVisible();
  await expect(page.locator("[data-message-id$=':user']")).toHaveCount(1);
  await expect(page.locator("[data-message-id$=':assistant']")).toHaveCount(1);
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
