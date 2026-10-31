import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type {
  ApiClient,
  PredefinedExecutionResponse,
  PredefinedListResponse,
  PredefinedQuery,
} from "../../api/client";
import { PredefinedQueriesPanel } from "./PredefinedQueriesPanel";

const query: PredefinedQuery = {
  id: 7,
  name: "Vendas por período",
  description: "Consulta de vendas.",
  sql: "SELECT month, total FROM sales WHERE month = :month",
  tags: ["vendas"],
  author: "admin@example.com",
  parameters: [
    { name: "month", label: "Mês", required: true },
  ],
  updated_at: "2025-01-15T10:00:00Z",
  is_favorite: false,
};

const executionResponse: PredefinedExecutionResponse = {
  query_id: 7,
  result: {
    columns: ["total"],
    rows: [{ total: 12 }],
    row_count: 1,
    truncated: false,
  },
};

function createClient(
  list: ApiClient["predefined"]["list"] = vi
    .fn()
    .mockResolvedValue({ queries: [query] }),
): ApiClient {
  return {
    auth: {
      me: vi.fn(),
      login: vi.fn(),
      signup: vi.fn(),
      logout: vi.fn(),
    },
    conversations: {
      list: vi.fn(),
      get: vi.fn(),
      create: vi.fn(),
      favorite: vi.fn(),
      delete: vi.fn(),
    },
    chat: {
      translate: vi.fn(),
      execute: vi.fn(),
      retry: vi.fn(),
    },
    history: {
      list: vi.fn(),
      pin: vi.fn(),
      delete: vi.fn(),
      rerun: vi.fn(),
    },
    predefined: {
      list,
      favorite: vi.fn().mockResolvedValue({ id: 7, is_favorite: true }),
      create: vi.fn().mockResolvedValue({ status: "created" }),
      update: vi.fn().mockResolvedValue({ status: "updated" }),
      delete: vi.fn().mockResolvedValue({ status: "deleted" }),
      execute: vi.fn().mockResolvedValue(executionResponse),
    },
    admin: {
      listUsers: vi.fn().mockResolvedValue({ profiles: [] }),
      updateStatus: vi.fn(),
      updateRole: vi.fn(),
    },
    schema: {
      sync: vi.fn().mockResolvedValue({ status: "synchronized" }),
    },
  };
}

describe("PredefinedQueriesPanel", () => {
  it("searches on submit without duplicate requests and renders an empty result", async () => {
    const empty: PredefinedListResponse = { queries: [] };
    const list = vi
      .fn()
      .mockResolvedValueOnce({ queries: [query] })
      .mockResolvedValueOnce(empty);
    const client = createClient(list);
    render(
      <PredefinedQueriesPanel
        client={client}
        role="user"
        onExecutionResult={vi.fn()}
      />,
    );

    await screen.findByRole("heading", { name: "Vendas por período" });
    fireEvent.change(screen.getByLabelText("Buscar consulta"), {
      target: { value: "inexistente" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Buscar" }));

    await screen.findByText("Nenhuma consulta encontrada.");
    expect(list).toHaveBeenCalledTimes(2);
    expect(list).toHaveBeenLastCalledWith("inexistente");
  });

  it("validates required parameters before execution and then forwards values", async () => {
    const onExecutionResult = vi.fn();
    const client = createClient();
    render(
      <PredefinedQueriesPanel
        client={client}
        role="user"
        onExecutionResult={onExecutionResult}
      />,
    );

    await screen.findByRole("heading", { name: "Vendas por período" });
    fireEvent.click(screen.getByRole("button", { name: "Executar" }));
    fireEvent.click(screen.getByRole("button", { name: "Executar consulta" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Informe o parâmetro Mês.");
    expect(client.predefined.execute).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("Mês *"), {
      target: { value: "2025-01" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Executar consulta" }));

    await waitFor(() =>
      expect(onExecutionResult).toHaveBeenCalledWith(executionResponse),
    );
    expect(client.predefined.execute).toHaveBeenCalledWith(7, {
      month: "2025-01",
    });
    expect(screen.getByRole("status")).toHaveTextContent(
      "Consulta compartilhada executada.",
    );
  });

  it("updates favorite state and hides management controls for regular users", async () => {
    const client = createClient();
    render(
      <PredefinedQueriesPanel
        client={client}
        role="user"
        onExecutionResult={vi.fn()}
      />,
    );

    await screen.findByRole("heading", { name: "Vendas por período" });
    fireEvent.click(screen.getByRole("button", { name: "Favoritar" }));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Desfavoritar" })).toBeInTheDocument(),
    );
    expect(client.predefined.favorite).toHaveBeenCalledWith(7, true);
    expect(screen.queryByRole("button", { name: "Nova consulta" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Editar" })).not.toBeInTheDocument();
  });

  it("shows CRUD controls for an authorized role and validates the editor", async () => {
    const client = createClient();
    render(
      <PredefinedQueriesPanel
        client={client}
        role="admin"
        onExecutionResult={vi.fn()}
      />,
    );

    await screen.findByRole("heading", { name: "Vendas por período" });
    fireEvent.click(screen.getByRole("button", { name: "Nova consulta" }));
    fireEvent.click(screen.getByRole("button", { name: "Salvar consulta" }));

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Informe nome e SQL para salvar a consulta.",
    );
    expect(client.predefined.create).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("Nome"), {
      target: { value: "Nova consulta" },
    });
    fireEvent.change(screen.getByLabelText("SQL somente leitura"), {
      target: { value: "SELECT 1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Salvar consulta" }));

    await waitFor(() =>
      expect(client.predefined.create).toHaveBeenCalledWith({
        name: "Nova consulta",
        description: "",
        sql: "SELECT 1",
        tags: [],
        parameters: [],
      }),
    );
  });
});
