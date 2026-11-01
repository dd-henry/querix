import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  ApiClient,
  ChatResponse,
  HistoryListResponse,
  HistoryRecord,
} from "../../api/client";
import { HistoryPanel } from "./HistoryPanel";

const records: HistoryRecord[] = [
  {
    id: 1,
    prompt: "Consulta antiga",
    sql: "SELECT 1",
    parameters: {},
    source: "chat",
    session_id: "conversation-1",
    is_pinned: false,
    created_at: "2025-01-15T10:00:00Z",
  },
  {
    id: 2,
    prompt: "Consulta fixada",
    sql: "SELECT 2",
    parameters: {},
    source: "predefined",
    session_id: null,
    is_pinned: true,
    created_at: "2024-01-15T10:00:00Z",
  },
];

const rerunResponse: ChatResponse = {
  conversation_id: "conversation-1",
  request_id: "request-1",
  status: "executed",
  content: "Aqui estão os resultados da consulta:",
  result: {
    columns: ["total"],
    rows: [{ total: 2 }],
    row_count: 1,
    truncated: false,
  },
  retryable: false,
  warnings: [],
};

function createClient(
  list: ApiClient["history"]["list"] = vi
    .fn()
    .mockResolvedValue({ records }),
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
      cancel: vi.fn(),
      retry: vi.fn(),
    },
    history: {
      list,
      pin: vi.fn().mockResolvedValue({ id: 1, is_pinned: true }),
      delete: vi.fn().mockResolvedValue({ id: 1, is_pinned: false }),
      rerun: vi.fn().mockResolvedValue(rerunResponse),
    },
    predefined: {
      list: vi.fn(),
      favorite: vi.fn(),
      create: vi.fn(),
      update: vi.fn(),
      delete: vi.fn(),
      execute: vi.fn(),
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

beforeEach(() => {
  vi.stubGlobal("crypto", {
    randomUUID: () => "generated-request",
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("HistoryPanel", () => {
  it("renders pinned records first and exposes source and SQL", async () => {
    render(
      <HistoryPanel
        client={createClient()}
        conversationId="conversation-1"
        onRerunResult={vi.fn()}
      />,
    );

    await screen.findByRole("heading", { name: "Consulta fixada" });
    expect(screen.getAllByRole("heading", { level: 3 })[0]).toHaveTextContent(
      "Consulta fixada",
    );
    expect(screen.getByText("Consulta compartilhada")).toBeInTheDocument();
    expect(screen.getByText("SELECT 1")).toBeInTheDocument();
  });

  it("shows an accessible empty state", async () => {
    const empty: HistoryListResponse = { records: [] };
    render(
      <HistoryPanel
        client={createClient(vi.fn().mockResolvedValue(empty))}
        onRerunResult={vi.fn()}
      />,
    );

    expect(await screen.findByText("Nenhuma consulta salva.")).toBeInTheDocument();
  });

  it("pins and deletes only after confirmation", async () => {
    const client = createClient();
    render(
      <HistoryPanel
        client={client}
        conversationId="conversation-1"
        onRerunResult={vi.fn()}
      />,
    );

    await screen.findByRole("heading", { name: "Consulta antiga" });
    fireEvent.click(screen.getByRole("button", { name: "Fixar" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Desafixar" })).toBeInTheDocument(),
    );
    expect(client.history.pin).toHaveBeenCalledWith(1, true);

    fireEvent.click(screen.getAllByRole("button", { name: "Excluir" })[0]);
    expect(
      screen.getByRole("group", {
        name: "Confirmar exclusão de Consulta antiga",
      }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(client.history.delete).not.toHaveBeenCalled();

    fireEvent.click(screen.getAllByRole("button", { name: "Excluir" })[0]);
    fireEvent.click(screen.getByRole("button", { name: "Confirmar exclusão" }));
    await waitFor(() =>
      expect(screen.queryByRole("heading", { name: "Consulta antiga" })).not.toBeInTheDocument(),
    );
    expect(client.history.delete).toHaveBeenCalledWith(1);
  });

  it("reruns a stored query in the active conversation", async () => {
    const onRerunResult = vi.fn();
    const client = createClient();
    render(
      <HistoryPanel
        client={client}
        conversationId="conversation-1"
        onRerunResult={onRerunResult}
      />,
    );

    await screen.findByRole("heading", { name: "Consulta antiga" });
    fireEvent.click(screen.getAllByRole("button", { name: "Reexecutar" })[1]);

    await waitFor(() =>
      expect(onRerunResult).toHaveBeenCalledWith(rerunResponse),
    );
    expect(client.history.rerun).toHaveBeenCalledWith(1, {
      conversation_id: "conversation-1",
      request_id: "generated-request",
    });
    expect(screen.getByRole("status")).toHaveTextContent(
      "Consulta enviada para a conversa.",
    );
  });

  it("offers retry after a load failure", async () => {
    const list = vi
      .fn()
      .mockRejectedValueOnce(new Error("network"))
      .mockResolvedValueOnce({ records });
    render(
      <HistoryPanel
        client={createClient(list)}
        onRerunResult={vi.fn()}
      />,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Não foi possível carregar o histórico.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Tentar novamente" }));
    await screen.findByRole("heading", { name: "Consulta fixada" });
    expect(list).toHaveBeenCalledTimes(2);
  });
});
