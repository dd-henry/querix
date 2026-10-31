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
    },
    schema: {
      sync: vi.fn().mockResolvedValue({ status: "synchronized" }),
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
      ),
    );
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
  });
});
