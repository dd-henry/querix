import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  ApiError,
  type AdminProfile,
  type ApiClient,
} from "../../api/client";
import { UserAdminPanel } from "./UserAdminPanel";

const profile: AdminProfile = {
  id: "user-1",
  email: "user@example.com",
  name: "User",
  role: "user",
  status: "approved",
  created_at: "2025-01-15T10:00:00Z",
  approved_at: "2025-01-15T10:05:00Z",
  disabled_at: null,
};

function createClient(
  overrides: Partial<ApiClient["admin"]> = {},
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
      listUsers: vi.fn().mockResolvedValue({ profiles: [profile] }),
      updateStatus: vi.fn().mockResolvedValue({
        id: profile.id,
        status: "disabled",
      }),
      updateRole: vi.fn().mockResolvedValue({
        id: profile.id,
        role: "admin",
      }),
      ...overrides,
    },
    schema: {
      sync: vi.fn().mockResolvedValue({ status: "synchronized" }),
    },
  };
}

describe("UserAdminPanel", () => {
  it("does not load or render for non-admin users", () => {
    const client = createClient();

    render(<UserAdminPanel client={client} role="dev" />);

    expect(screen.queryByRole("heading")).not.toBeInTheDocument();
    expect(client.admin.listUsers).not.toHaveBeenCalled();
  });

  it("updates status and role without replacing the loaded list", async () => {
    const client = createClient();
    render(<UserAdminPanel client={client} role="admin" />);

    await screen.findByRole("heading", { name: "User" });
    const status = screen.getByLabelText("Status de user@example.com");
    fireEvent.change(status, { target: { value: "disabled" } });
    fireEvent.click(screen.getByRole("button", { name: "Atualizar status" }));

    await waitFor(() =>
      expect(client.admin.updateStatus).toHaveBeenCalledWith(
        "user-1",
        "disabled",
      ),
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "Status de user@example.com atualizado.",
    );

    const role = screen.getByLabelText("Papel de user@example.com");
    fireEvent.change(role, { target: { value: "admin" } });
    fireEvent.click(screen.getByRole("button", { name: "Atualizar papel" }));

    await waitFor(() =>
      expect(client.admin.updateRole).toHaveBeenCalledWith("user-1", "admin"),
    );
    expect(screen.getByRole("heading", { name: "User" })).toBeInTheDocument();
  });

  it("rejects unsupported status values before calling the API", async () => {
    const client = createClient();
    render(<UserAdminPanel client={client} role="admin" />);

    await screen.findByRole("heading", { name: "User" });
    fireEvent.change(screen.getByLabelText("Status de user@example.com"), {
      target: { value: "pending" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Atualizar status" }));

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Selecione um status válido",
    );
    expect(client.admin.updateStatus).not.toHaveBeenCalled();
  });

  it("turns the last-admin conflict into an actionable error", async () => {
    const updateRole = vi
      .fn()
      .mockRejectedValue(
        new ApiError(
          "last_admin_conflict",
          "O último administrador aprovado não pode ser removido.",
          409,
        ),
      );
    const client = createClient({ updateRole });
    render(<UserAdminPanel client={client} role="admin" />);

    await screen.findByRole("heading", { name: "User" });
    fireEvent.change(screen.getByLabelText("Papel de user@example.com"), {
      target: { value: "admin" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Atualizar papel" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Aprove outro administrador antes de remover este acesso.",
      ),
    );
  });
});
