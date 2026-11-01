import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApiError, type ApiClient } from "../../api/client";
import { SyncDatabaseButton } from "./SyncDatabaseButton";

function createClient(
  sync: ApiClient["schema"]["sync"] = vi
    .fn()
    .mockResolvedValue({ status: "synchronized" }),
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
      list: vi.fn(),
      pin: vi.fn(),
      delete: vi.fn(),
      rerun: vi.fn(),
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
      listUsers: vi.fn(),
      updateStatus: vi.fn(),
      updateRole: vi.fn(),
    },
    schema: { sync },
  };
}

describe("SyncDatabaseButton", () => {
  it("disables duplicate submissions and invalidates dependent data after success", async () => {
    let resolveSync!: (value: { status: "synchronized" }) => void;
    const sync = vi.fn(
      () =>
        new Promise<{ status: "synchronized" }>((resolve) => {
          resolveSync = resolve;
        }),
    );
    const onSynced = vi.fn();
    const client = createClient(sync);
    render(<SyncDatabaseButton client={client} onSynced={onSynced} />);

    const button = screen.getByRole("button", { name: "Sincronizar Banco" });
    fireEvent.click(button);
    fireEvent.click(button);

    expect(sync).toHaveBeenCalledOnce();
    expect(button).toBeDisabled();
    expect(button).toHaveTextContent("Sincronizando...");

    resolveSync({ status: "synchronized" });
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent(
        "Banco sincronizado com sucesso.",
      ),
    );
    expect(onSynced).toHaveBeenCalledOnce();
    expect(button).toBeEnabled();
  });

  it("shows failure feedback without claiming synchronization", async () => {
    const sync = vi
      .fn()
      .mockRejectedValue(
        new ApiError(
          "schema_sync_failed",
          "O schema não pôde ser sincronizado.",
          503,
        ),
      );
    const client = createClient(sync);
    render(<SyncDatabaseButton client={client} />);

    fireEvent.click(screen.getByRole("button", { name: "Sincronizar Banco" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        "O schema não pôde ser sincronizado.",
      ),
    );
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
