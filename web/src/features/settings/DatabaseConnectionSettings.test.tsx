import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApiError, type ApiClient } from "../../api/client";
import { DatabaseConnectionSettings } from "./DatabaseConnectionSettings";

function createClient(
  get: ApiClient["settings"]["database"]["get"] = vi
    .fn()
    .mockResolvedValue({ configured: false, updated_at: null }),
  save: ApiClient["settings"]["database"]["save"] = vi
    .fn()
    .mockResolvedValue({ configured: true, updated_at: null }),
): Pick<ApiClient, "settings"> {
  return {
    settings: {
      database: { get, save },
    },
  };
}

describe("DatabaseConnectionSettings", () => {
  it("loads status and saves a connection without echoing the secret", async () => {
    const get = vi.fn().mockResolvedValue({
      configured: false,
      updated_at: null,
    });
    const save = vi.fn().mockResolvedValue({
      configured: true,
      updated_at: "2026-11-12T12:00:00Z",
    });
    const client = createClient(get, save);
    render(<DatabaseConnectionSettings client={client} />);

    await waitFor(() =>
      expect(
        screen.getByText("Nenhuma conexão global está configurada."),
      ).toBeInTheDocument(),
    );
    const secret = "postgresql://user:pass@target.example/analytics";
    const input = screen.getByLabelText("Connection string PostgreSQL");
    fireEvent.change(input, { target: { value: secret } });
    fireEvent.click(
      screen.getByRole("button", { name: "Testar e salvar conexão" }),
    );

    await waitFor(() =>
      expect(
        screen.getByText("Conexão com o banco configurada com sucesso."),
      ).toBeInTheDocument(),
    );
    expect(save).toHaveBeenCalledWith(secret);
    expect(input).toHaveValue("");
  });

  it("blocks duplicate submissions while testing the connection", async () => {
    let resolveSave!: (value: { configured: true; updated_at: null }) => void;
    const save = vi.fn(
      () =>
        new Promise<{ configured: true; updated_at: null }>((resolve) => {
          resolveSave = resolve;
        }),
    );
    const client = createClient(vi.fn().mockResolvedValue({ configured: false }), save);
    render(<DatabaseConnectionSettings client={client} />);
    const input = screen.getByLabelText("Connection string PostgreSQL");
    fireEvent.change(input, {
      target: { value: "postgresql://target.example/analytics" },
    });
    const button = screen.getByRole("button", {
      name: "Testar e salvar conexão",
    });

    fireEvent.click(button);
    fireEvent.click(button);

    expect(save).toHaveBeenCalledOnce();
    expect(button).toBeDisabled();
    resolveSave({ configured: true, updated_at: null });
    await waitFor(() => expect(button).toBeEnabled());
  });

  it("shows failed connection feedback without claiming success", async () => {
    const save = vi.fn().mockRejectedValue(
      new ApiError(
        "database_connection_failed",
        "A conexão não pôde ser estabelecida.",
        503,
      ),
    );
    const client = createClient(
      vi.fn().mockResolvedValue({ configured: false }),
      save,
    );
    render(<DatabaseConnectionSettings client={client} />);
    fireEvent.change(screen.getByLabelText("Connection string PostgreSQL"), {
      target: { value: "postgresql://target.example/analytics" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Testar e salvar conexão" }),
    );

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        "A conexão não pôde ser estabelecida.",
      ),
    );
    expect(
      screen.queryByText("Conexão com o banco configurada com sucesso."),
    ).not.toBeInTheDocument();
  });
});
