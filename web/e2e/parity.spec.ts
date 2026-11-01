import { expect, test, type Page } from "@playwright/test";

const adminProfile = {
  id: "admin-1",
  email: "admin@example.com",
  name: "Admin",
  role: "admin",
  status: "approved",
};

const conversation = {
  id: "conversation-1",
  title: "Pedidos em aberto",
  is_favorite: false,
  created_at: "2025-01-15T10:00:00Z",
  last_activity: "2025-01-15T10:30:00Z",
};

const historyRecord = {
  id: 11,
  prompt: "Pedidos em aberto",
  sql: "SELECT * FROM orders",
  parameters: {},
  source: "chat",
  session_id: "conversation-1",
  is_pinned: false,
  created_at: "2025-01-15T10:00:00Z",
};

const predefinedQuery = {
  id: 7,
  name: "Vendas por período",
  description: "Consulta de vendas.",
  sql: "SELECT month, total FROM sales",
  tags: ["vendas"],
  author: "admin@example.com",
  parameters: [],
  updated_at: "2025-01-15T10:00:00Z",
  is_favorite: false,
};

async function mockAdminApi(
  page: Page,
  title = conversation.title,
  profile = adminProfile,
) {
  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(profile),
    });
  });
  await page.route("**/api/conversations/conversation-1", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ...conversation,
        title,
        messages: [
          {
            id: 1,
            request_id: "request-1",
            role: "user",
            content: "Pedidos em aberto",
            sql: null,
            error: null,
            metadata: {},
            created_at: "2025-01-15T10:00:00Z",
          },
          {
            id: 2,
            request_id: "request-1",
            role: "assistant",
            content: "Consulta carregada.",
            sql: "SELECT * FROM orders",
            error: null,
            metadata: { retryable: false },
            created_at: "2025-01-15T10:00:01Z",
          },
        ],
      }),
    });
  });
  await page.route("**/api/conversations?*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        groups: [
          {
            key: "today",
            label: "Hoje",
            conversations: [{ ...conversation, title }],
          },
        ],
        expired_count: 0,
      }),
    });
  });
  await page.route("**/api/chat/execute", async (route) => {
    expect(route.request().postDataJSON()).toEqual({
      conversation_id: "conversation-1",
      request_id: "request-1",
    });
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        conversation_id: "conversation-1",
        request_id: "request-1",
        status: "executed",
        content: "Resultado atualizado.",
        sql: "SELECT * FROM orders",
        summary: "A consulta retornou dados atuais.",
        retryable: false,
        warnings: [],
        result: {
          columns: ["total"],
          rows: [{ total: 3 }],
          row_count: 1,
          truncated: false,
        },
      }),
    });
  });
  await page.route("**/api/history", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ records: [historyRecord] }),
    });
  });
  await page.route("**/api/history/*/rerun", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        conversation_id: "conversation-1",
        request_id: "request-rerun",
        status: "executed",
        content: "Consulta repetida.",
        result: {
          columns: ["total"],
          rows: [{ total: 3 }],
          row_count: 1,
          truncated: false,
        },
        retryable: false,
        warnings: [],
      }),
    });
  });
  await page.route("**/api/predefined-queries*", async (route) => {
    const url = route.request().url();
    if (url.endsWith("/execute")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          query_id: 7,
          result: {
            columns: ["total"],
            rows: [{ total: 12 }],
            row_count: 1,
            truncated: false,
          },
        }),
      });
      return;
    }
    if (route.request().method() === "PATCH") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ id: 7, is_favorite: true }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ queries: [predefinedQuery] }),
    });
  });
  await page.route("**/api/predefined-queries/7/execute", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        query_id: 7,
        result: {
          columns: ["total"],
          rows: [{ total: 12 }],
          row_count: 1,
          truncated: false,
        },
      }),
    });
  });
  await page.route("**/api/admin/users", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        profiles: [
          {
            id: "user-2",
            email: "user@example.com",
            name: "User",
            role: "user",
            status: "approved",
            created_at: "2025-01-15T10:00:00Z",
            approved_at: "2025-01-15T10:00:00Z",
            disabled_at: null,
          },
        ],
      }),
    });
  });
  await page.route("**/api/admin/users/*/status", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ id: "user-2", status: "disabled" }),
    });
  });
  await page.route("**/api/admin/users/*/role", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ id: "user-2", role: "dev" }),
    });
  });
  await page.route("**/api/schema/sync", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "synchronized" }),
    });
  });
}

async function mockUserFailureApi(page: Page) {
  const userProfile = {
    id: "user-3",
    email: "reader@example.com",
    name: "Reader",
    role: "user",
    status: "approved",
  };
  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(userProfile),
    });
  });
  await page.route("**/api/conversations?*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ groups: [], expired_count: 0 }),
    });
  });
  await page.route("**/api/history", async (route) => {
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        error: {
          code: "storage_unavailable",
          message: "Histórico indisponível.",
        },
      }),
    });
  });
  await page.route("**/api/predefined-queries*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ queries: [predefinedQuery] }),
    });
  });
  await page.route("**/api/schema/sync", async (route) => {
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        error: {
          code: "schema_sync_failed",
          message: "Sincronização indisponível.",
        },
      }),
    });
  });
}

test("covers conversation resume, parity panels, sync, and mobile navigation", async ({
  page,
}) => {
  await mockAdminApi(page);
  await page.goto("/");

  await expect(
    page.getByRole("button", { name: "Abrir conversa Pedidos em aberto" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Abrir conversa Pedidos em aberto" })
    .click();
  await expect(page.getByText("Consulta carregada.")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Reexecutar consulta" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Reexecutar consulta" }).click();
  await expect(page.getByText("Resultado atualizado.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Resultados" })).toBeVisible();
  await expect(page.locator("[data-message-id$=':user']")).toHaveCount(1);
  await expect(page.locator("[data-message-id$=':assistant']")).toHaveCount(1);

  await page.getByRole("button", { name: "Histórico" }).click();
  await expect(
    page.getByRole("heading", { name: "Histórico", level: 1 }),
  ).toBeVisible();
  await expect(page.getByText("SELECT * FROM orders")).toBeVisible();
  await page.getByRole("button", { name: "Reexecutar" }).click();
  await expect(page.getByText("Consulta repetida.")).toBeVisible();

  await page.getByRole("button", { name: "Consultas compartilhadas" }).click();
  await expect(page.getByRole("heading", { name: "Vendas por período" })).toBeVisible();
  await page.getByRole("button", { name: "Executar" }).click();
  await expect(page.getByText("Resultado da consulta compartilhada.")).toBeVisible();

  await page.getByRole("button", { name: "Administração" }).click();
  await expect(page.getByText("user@example.com", { exact: true })).toBeVisible();
  await page
    .getByLabel("Status de user@example.com")
    .selectOption("disabled");
  await page.getByRole("button", { name: "Atualizar status" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Status de user@example.com atualizado.",
  );

  await page.getByRole("button", { name: "Configurações" }).click();
  await page.getByRole("button", { name: "Sincronizar Banco" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Banco sincronizado com sucesso.",
  );

  await page.setViewportSize({ width: 360, height: 800 });
  await page.getByRole("button", { name: "Abrir navegação" }).click();
  await expect(
    page.getByRole("button", { name: "Fechar navegação" }),
  ).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBe(true);
});

test("keeps conversation lists scoped to each browser session", async ({
  browser,
}) => {
  const firstContext = await browser.newContext();
  const secondContext = await browser.newContext();
  const firstPage = await firstContext.newPage();
  const secondPage = await secondContext.newPage();
  await mockAdminApi(firstPage, "Primeira conversa", {
    ...adminProfile,
    id: "admin-1",
    email: "first@example.com",
  });
  await mockAdminApi(secondPage, "Segunda conversa", {
    ...adminProfile,
    id: "admin-2",
    email: "second@example.com",
  });

  await firstPage.goto("/");
  await secondPage.goto("/");
  await expect(
    firstPage.getByRole("button", { name: "Abrir conversa Primeira conversa" }),
  ).toBeVisible();
  await expect(
    secondPage.getByRole("button", { name: "Abrir conversa Segunda conversa" }),
  ).toBeVisible();
  await expect(
    firstPage.getByRole("button", { name: "Abrir conversa Segunda conversa" }),
  ).toHaveCount(0);
  await expect(
    secondPage.getByRole("button", { name: "Abrir conversa Primeira conversa" }),
  ).toHaveCount(0);

  await firstContext.close();
  await secondContext.close();
});

test("shows feature failures and enforces user-role navigation in a mobile keyboard flow", async ({
  page,
}) => {
  await mockUserFailureApi(page);
  await page.goto("/");

  await expect(
    page.getByRole("button", { name: "Administração" }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Histórico" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Histórico indisponível.",
  );

  await page
    .getByRole("button", { name: "Consultas compartilhadas" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Vendas por período" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Nova consulta" }),
  ).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Editar" })).toHaveCount(0);

  await page.getByRole("button", { name: "Configurações" }).click();
  await page.getByRole("button", { name: "Sincronizar Banco" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Sincronização indisponível.",
  );
  await expect(page.getByRole("main").getByRole("status")).toHaveCount(0);

  await page.setViewportSize({ width: 360, height: 800 });
  await page.getByRole("button", { name: "Abrir navegação" }).click();
  const historyButton = page.getByRole("button", { name: "Histórico" });
  await historyButton.focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("heading", { name: "Histórico", level: 1 }),
  ).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBe(true);
});
