import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ApiClient, Profile } from "../api/client";
import { AuthenticatedApp } from "./AuthenticatedApp";

const profile: Profile = {
  id: "admin-1",
  email: "admin@example.com",
  name: "Admin",
  role: "admin",
  status: "approved",
};

function createClient(): ApiClient {
  return {
    auth: {
      me: vi.fn(),
      login: vi.fn(),
      signup: vi.fn(),
      changePassword: vi.fn(),
      logout: vi.fn(),
    },
    conversations: {
      list: vi.fn().mockResolvedValue({ groups: [], expired_count: 0 }),
      get: vi.fn(),
      create: vi.fn(),
      favorite: vi.fn(),
      delete: vi.fn(),
    },
    chat: {
      translate: vi.fn(),
      execute: vi.fn(),
      cancel: vi.fn().mockResolvedValue({ status: "cancelled" }),
      retry: vi.fn(),
    },
    history: {
      list: vi.fn().mockResolvedValue({ records: [] }),
      pin: vi.fn(),
      delete: vi.fn(),
      rerun: vi.fn(),
    },
    predefined: {
      list: vi.fn().mockResolvedValue({ queries: [] }),
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
      resetPassword: vi.fn(),
    },
    schema: {
      sync: vi.fn().mockResolvedValue({ status: "synchronized" }),
    },
    settings: {
      database: {
        get: vi.fn().mockResolvedValue({ configured: false, updated_at: null }),
        save: vi.fn(),
      },
    },
  };
}

describe("AuthenticatedApp", () => {
  it("uses automatic execution for the normal chat flow", async () => {
    const client = createClient();
    vi.mocked(client.chat.translate).mockResolvedValue({
      conversation_id: "conversation-1",
      request_id: "request-1",
      status: "executed",
      content: "Aqui estão os resultados da consulta:",
      retryable: false,
      warnings: [],
    });
    render(
      <AuthenticatedApp
        client={client}
        profile={profile}
        onSignOut={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText("Pergunte sobre seus dados"), {
      target: { value: "Qual foi o faturamento?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Enviar pergunta" }));

    await waitFor(() =>
      expect(client.chat.translate).toHaveBeenCalledWith(
        expect.objectContaining({ review_mode: false }),
        { signal: expect.any(AbortSignal) },
      ),
    );
  });

  it("shows a recent chat result again after switching conversations", async () => {
    const client = createClient();
    const createdAt = "2025-01-15T10:00:00Z";
    const first = {
      id: "conversation-1",
      title: "Primeira conversa",
      is_favorite: false,
      created_at: createdAt,
      last_activity: createdAt,
    };
    const second = { ...first, id: "conversation-2", title: "Outra conversa" };
    vi.mocked(client.conversations.list).mockResolvedValue({
      groups: [{ key: "today", label: "Hoje", conversations: [first, second] }],
      expired_count: 0,
    });
    let requestId = "";
    vi.mocked(client.conversations.get).mockImplementation(async (id) => ({
      ...(id === first.id ? first : second),
      messages: id === first.id && requestId
        ? [
            { id: 1, request_id: requestId, role: "user", content: "Qual o total?", metadata: {}, created_at: createdAt },
            { id: 2, request_id: requestId, role: "assistant", content: "Resultado.", sql: "SELECT 42 AS total", metadata: {}, created_at: createdAt },
          ]
        : [],
    }));
    vi.mocked(client.chat.translate).mockImplementation(async (input) => {
      requestId = input.request_id;
      return {
        conversation_id: first.id,
        request_id: requestId,
        status: "executed",
        content: "Resultado.",
        sql: "SELECT 42 AS total",
        result: { columns: ["total"], rows: [{ total: 42 }], row_count: 1, truncated: false },
        retryable: false,
        warnings: [],
      };
    });
    render(<AuthenticatedApp client={client} profile={profile} onSignOut={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: "Abrir conversa Primeira conversa" }));
    await waitFor(() => expect(client.conversations.get).toHaveBeenCalledWith(first.id));
    fireEvent.change(screen.getByLabelText("Pergunte sobre seus dados"), {
      target: { value: "Qual o total?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Enviar pergunta" }));
    expect(await screen.findByRole("cell", { name: "42" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Abrir conversa Outra conversa" }));
    await waitFor(() => expect(screen.queryByRole("cell", { name: "42" })).not.toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Abrir conversa Primeira conversa" }));
    expect(await screen.findByRole("cell", { name: "42" })).toBeInTheDocument();
    expect(client.chat.translate).toHaveBeenCalledTimes(1);
    expect(client.chat.execute).not.toHaveBeenCalled();
  });

  it("switches accessible panels and moves focus to the opened panel", async () => {
    render(
      <AuthenticatedApp
        client={createClient()}
        profile={profile}
        onSignOut={vi.fn()}
      />,
    );

    await screen.findByRole("heading", {
      level: 1,
      name: "Converse com seus dados",
    });
    fireEvent.click(screen.getByRole("button", { name: "Histórico" }));

    await waitFor(() =>
      expect(
        screen.getByRole("heading", { level: 1, name: "Histórico" }),
      ).toBeInTheDocument(),
    );
    expect(document.activeElement).toHaveClass("authenticated-panel");
    expect(screen.getByRole("button", { name: "Histórico" })).toHaveAttribute(
      "aria-current",
      "page",
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Consultas compartilhadas" }),
    );
    await screen.findByRole("heading", {
      level: 1,
      name: "Consultas compartilhadas",
    });
    fireEvent.click(screen.getByRole("button", { name: "Administração" }));
    await screen.findByRole("heading", {
      level: 1,
      name: "Administração de usuários",
    });
    fireEvent.click(screen.getByRole("button", { name: "Configurações" }));
    await screen.findByRole("heading", { level: 1, name: "Configurações" });
    expect(
      screen.getByRole("button", { name: "Sincronizar Banco" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        name: "Conexão consultada pelo Querix",
      }),
    ).toBeInTheDocument();
  });

  it("does not render database connection editing for non-admin users", async () => {
    render(
      <AuthenticatedApp
        client={createClient()}
        profile={{ ...profile, role: "user" }}
        onSignOut={vi.fn()}
      />,
    );

    await screen.findByRole("heading", {
      level: 1,
      name: "Converse com seus dados",
    });
    fireEvent.click(screen.getByRole("button", { name: "Configurações" }));
    await screen.findByRole("heading", { level: 1, name: "Configurações" });

    expect(
      screen.queryByRole("heading", {
        name: "Conexão consultada pelo Querix",
      }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Sincronizar Banco" }),
    ).toBeInTheDocument();
  });
});
