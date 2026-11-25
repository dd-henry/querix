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
      changePassword: vi.fn(),
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
      resetPassword: vi.fn().mockResolvedValue({
        id: profile.id,
        temporary_password: "temp-1234",
      }),
      ...overrides,
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

describe("UserAdminPanel", () => {
  it("does not load or render for non-admin users", () => {
    const client = createClient();

    render(<UserAdminPanel client={client} role="dev" />);

    expect(screen.queryByRole("heading")).not.toBeInTheDocument();
    expect(client.admin.listUsers).not.toHaveBeenCalled();
  });

  it("shows a loading error without claiming that no users exist", async () => {
    const listUsers = vi.fn().mockRejectedValue(
      new ApiError("internal_error", "Internal server error.", 500),
    );
    render(<UserAdminPanel client={createClient({ listUsers })} role="admin" />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Internal server error.",
    );
    expect(screen.queryByText("Nenhum usuário encontrado.")).not.toBeInTheDocument();
  });

  it("shows an empty state after a successful empty response", async () => {
    const listUsers = vi.fn().mockResolvedValue({ profiles: [] });
    render(<UserAdminPanel client={createClient({ listUsers })} role="admin" />);

    expect(await screen.findByText("Nenhum usuário encontrado.")).toBeInTheDocument();
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

  it("resets a password and shows the temporary password once", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const client = createClient();
    render(<UserAdminPanel client={client} role="admin" />);

    await screen.findByRole("heading", { name: "User" });
    fireEvent.click(
      screen.getByRole("button", { name: "Resetar senha de user@example.com" }),
    );

    await waitFor(() =>
      expect(client.admin.resetPassword).toHaveBeenCalledWith("user-1"),
    );
    expect(await screen.findByRole("status")).toHaveTextContent("temp-1234");
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
