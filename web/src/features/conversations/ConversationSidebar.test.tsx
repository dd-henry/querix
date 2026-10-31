import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ApiClient, ConversationListResponse } from "../../api/client";
import { ConversationSidebar } from "./ConversationSidebar";

const conversations: ConversationListResponse = {
  expired_count: 0,
  groups: [
    {
      key: "today",
      label: "Hoje",
      conversations: [
        {
          id: "conversation-1",
          title: "Pedidos em aberto",
          is_favorite: false,
          created_at: "2025-01-15T10:00:00Z",
          last_activity: "2025-01-15T10:30:00Z",
        },
      ],
    },
    {
      key: "yesterday",
      label: "Ontem",
      conversations: [],
    },
    {
      key: "last_7_days",
      label: "Últimos 7 dias",
      conversations: [],
    },
    {
      key: "last_30_days",
      label: "Últimos 30 dias",
      conversations: [],
    },
    {
      key: "older",
      label: "Mais antigas",
      conversations: [],
    },
  ],
};

function createClient(
  list: ApiClient["conversations"]["list"] = vi
    .fn()
    .mockResolvedValue(conversations),
): ApiClient {
  return {
    auth: {
      me: vi.fn(),
      login: vi.fn(),
      signup: vi.fn(),
      logout: vi.fn(),
    },
    conversations: {
      list,
      get: vi.fn(),
      create: vi.fn(),
      favorite: vi.fn().mockResolvedValue(conversations.groups[0].conversations[0]),
      delete: vi.fn().mockResolvedValue(undefined),
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
  };
}

describe("ConversationSidebar", () => {
  it("renders grouped conversations and requests the browser timezone", async () => {
    const list = vi.fn().mockResolvedValue(conversations);
    render(<ConversationSidebar client={createClient(list)} />);

    await screen.findByRole("button", { name: "Abrir conversa Pedidos em aberto" });

    expect(screen.getByRole("heading", { name: "Hoje" })).toBeInTheDocument();
    expect(list).toHaveBeenCalledWith(
      Intl.DateTimeFormat().resolvedOptions().timeZone,
    );
    expect(screen.queryByRole("heading", { name: "Ontem" })).not.toBeInTheDocument();
  });

  it("shows an empty state and starts a new conversation", async () => {
    const onNewConversation = vi.fn();
    const emptyResponse: ConversationListResponse = {
      expired_count: 0,
      groups: conversations.groups.map((group) => ({
        ...group,
        conversations: [],
      })),
    };
    const list = vi.fn().mockResolvedValue(emptyResponse);
    render(
      <ConversationSidebar
        client={createClient(list)}
        onNewConversation={onNewConversation}
      />,
    );

    await screen.findByText("Nenhuma conversa ainda.");
    fireEvent.click(screen.getByRole("button", { name: "Nova conversa" }));

    expect(onNewConversation).toHaveBeenCalledOnce();
  });

  it("selects a conversation and closes the mobile drawer", async () => {
    const onSelect = vi.fn();
    const onCloseMobile = vi.fn();
    render(
      <ConversationSidebar
        client={createClient()}
        onSelect={onSelect}
        onCloseMobile={onCloseMobile}
      />,
    );

    fireEvent.click(
      await screen.findByRole("button", {
        name: "Abrir conversa Pedidos em aberto",
      }),
    );

    expect(onSelect).toHaveBeenCalledWith("conversation-1");
    expect(onCloseMobile).toHaveBeenCalledOnce();
  });

  it("favorites a conversation without reloading the list", async () => {
    const favorite = vi.fn().mockResolvedValue({
      ...conversations.groups[0].conversations[0],
      is_favorite: true,
    });
    const client = createClient();
    client.conversations.favorite = favorite;
    render(<ConversationSidebar client={client} />);

    const favoriteButton = await screen.findByRole("button", {
      name: "Favoritar Pedidos em aberto",
    });
    fireEvent.click(favoriteButton);

    await waitFor(() =>
      expect(
        screen.getByRole("button", {
          name: "Desfavoritar Pedidos em aberto",
        }),
      ).toBeInTheDocument(),
    );
    expect(favorite).toHaveBeenCalledWith("conversation-1", true);
    expect(client.conversations.list).toHaveBeenCalledOnce();
  });

  it("requires confirmation before deleting a conversation", async () => {
    const client = createClient();
    render(<ConversationSidebar client={client} />);

    fireEvent.click(
      await screen.findByRole("button", {
        name: "Excluir Pedidos em aberto",
      }),
    );
    expect(
      screen.getByRole("group", {
        name: "Confirmar exclusão de Pedidos em aberto",
      }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(
      screen.queryByRole("group", {
        name: "Confirmar exclusão de Pedidos em aberto",
      }),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Excluir Pedidos em aberto" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirmar exclusão" }));
    await waitFor(() =>
      expect(
        screen.queryByRole("button", {
          name: "Abrir conversa Pedidos em aberto",
        }),
      ).not.toBeInTheDocument(),
    );
    expect(client.conversations.delete).toHaveBeenCalledWith("conversation-1");
  });

  it("offers retry after a list failure", async () => {
    const list = vi
      .fn()
      .mockRejectedValueOnce(new Error("network"))
      .mockResolvedValueOnce(conversations);
    render(<ConversationSidebar client={createClient(list)} />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Não foi possível carregar as conversas.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Tentar novamente" }));

    await screen.findByRole("button", {
      name: "Abrir conversa Pedidos em aberto",
    });
    expect(list).toHaveBeenCalledTimes(2);
  });
});
