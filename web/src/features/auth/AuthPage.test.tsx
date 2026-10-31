import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApiError, type ApiClient, type Profile } from "../../api/client";
import {
  AuthProvider,
  AuthRouter,
} from "../../app/AuthProvider";
import { AuthPage } from "./AuthPage";

const approvedProfile: Profile = {
  id: "user-1",
  email: "user@example.com",
  name: "User",
  role: "user",
  status: "approved",
};

function createClient(
  overrides: Partial<ApiClient["auth"]> = {},
): ApiClient {
  return {
    auth: {
      me: vi.fn().mockRejectedValue(
        new ApiError("auth_required", "Authentication required.", 401),
      ),
      login: vi.fn(),
      signup: vi.fn(),
      logout: vi.fn().mockResolvedValue({ message: "Logged out." }),
      ...overrides,
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
  };
}

function renderPage(client: ApiClient) {
  render(
    <AuthProvider client={client}>
      {() => (
        <AuthRouter
          publicView={<AuthPage />}
          authenticatedView={() => <div data-testid="chat">Chat</div>}
          blockedView={(message) => <div>{message}</div>}
        />
      )}
    </AuthProvider>,
  );
}

async function waitForLoginPage() {
  await screen.findByRole("tab", { name: "Entrar" });
}

function switchToSignup() {
  fireEvent.click(screen.getByRole("tab", { name: "Criar conta" }));
}

describe("AuthPage", () => {
  it("does not call the API for empty signup name or email", async () => {
    const signup = vi.fn();
    renderPage(createClient({ signup }));
    await waitForLoginPage();
    switchToSignup();

    fireEvent.click(
      screen.getByRole("button", { name: "Solicitar acesso" }),
    );

    expect(signup).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Informe nome e email.",
    );
  });

  it("does not call the API for a short signup password", async () => {
    const signup = vi.fn();
    renderPage(createClient({ signup }));
    await waitForLoginPage();
    switchToSignup();

    fireEvent.change(screen.getByLabelText("Nome completo"), {
      target: { value: "New User" },
    });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "new@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Senha"), {
      target: { value: "short" },
    });
    fireEvent.change(screen.getByLabelText("Confirmar senha"), {
      target: { value: "short" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Solicitar acesso" }),
    );

    expect(signup).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "A senha deve ter pelo menos 8 caracteres.",
    );
  });

  it("does not call the API when signup confirmation differs", async () => {
    const signup = vi.fn();
    renderPage(createClient({ signup }));
    await waitForLoginPage();
    switchToSignup();

    fireEvent.change(screen.getByLabelText("Nome completo"), {
      target: { value: "New User" },
    });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "new@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Senha"), {
      target: { value: "password" },
    });
    fireEvent.change(screen.getByLabelText("Confirmar senha"), {
      target: { value: "different" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Solicitar acesso" }),
    );

    expect(signup).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "As senhas não conferem.",
    );
  });

  it("retains email, clears password, and shows the login prefix on failure", async () => {
    const login = vi.fn().mockRejectedValue(
      new ApiError("auth_failed", "Email ou senha inválidos.", 401),
    );
    renderPage(createClient({ login }));
    await waitForLoginPage();

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "user@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Senha"), {
      target: { value: "wrong-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Entrar" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Não foi possível entrar: Email ou senha inválidos.",
      ),
    );
    expect(screen.getByLabelText("Email")).toHaveValue(
      "user@example.com",
    );
    expect(screen.getByLabelText("Senha")).toHaveValue("");
    expect(login).toHaveBeenCalledWith({
      email: "user@example.com",
      password: "wrong-password",
    });
  });

  it("transitions to chat after a successful login", async () => {
    const login = vi.fn().mockResolvedValue(approvedProfile);
    renderPage(createClient({ login }));
    await waitForLoginPage();

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "user@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Senha"), {
      target: { value: "password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Entrar" }));

    await waitFor(() =>
      expect(screen.getByTestId("chat")).toBeInTheDocument(),
    );
    expect(login).toHaveBeenCalledOnce();
  });

  it("shows the signup success message", async () => {
    const signup = vi.fn().mockResolvedValue({
      message:
        "Cadastro recebido. Confirme seu email e aguarde a aprovação de um admin.",
    });
    renderPage(createClient({ signup }));
    await waitForLoginPage();
    switchToSignup();

    fireEvent.change(screen.getByLabelText("Nome completo"), {
      target: { value: "New User" },
    });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "new@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Senha"), {
      target: { value: "password" },
    });
    fireEvent.change(screen.getByLabelText("Confirmar senha"), {
      target: { value: "password" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Solicitar acesso" }),
    );

    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent(
        "Cadastro recebido. Confirme seu email e aguarde a aprovação de um admin.",
      ),
    );
    expect(signup).toHaveBeenCalledWith({
      name: "New User",
      email: "new@example.com",
      password: "password",
      password_confirmation: "password",
    });
  });

  it("shows signup failures inline", async () => {
    const signup = vi.fn().mockRejectedValue(
      new ApiError("signup_failed", "Email já cadastrado.", 502),
    );
    renderPage(createClient({ signup }));
    await waitForLoginPage();
    switchToSignup();

    fireEvent.change(screen.getByLabelText("Nome completo"), {
      target: { value: "New User" },
    });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "new@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Senha"), {
      target: { value: "password" },
    });
    fireEvent.change(screen.getByLabelText("Confirmar senha"), {
      target: { value: "password" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Solicitar acesso" }),
    );

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Não foi possível criar conta: Email já cadastrado.",
      ),
    );
  });

  it("prevents duplicate login submissions while the request is active", async () => {
    let resolveLogin!: (profile: Profile) => void;
    const login = vi.fn(
      () =>
        new Promise<Profile>((resolve) => {
          resolveLogin = resolve;
        }),
    );
    renderPage(createClient({ login }));
    await waitForLoginPage();

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "user@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Senha"), {
      target: { value: "password" },
    });
    const submit = screen.getByRole("button", { name: "Entrar" });
    fireEvent.click(submit);
    fireEvent.click(submit);

    expect(login).toHaveBeenCalledOnce();
    expect(screen.getByRole("button", { name: "Entrando..." })).toBeDisabled();

    resolveLogin(approvedProfile);
    await waitFor(() =>
      expect(screen.getByTestId("chat")).toBeInTheDocument(),
    );
  });
});
