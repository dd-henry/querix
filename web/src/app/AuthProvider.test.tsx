import { StrictMode } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApiError, type ApiClient, type Profile } from "../api/client";
import {
  AuthProvider,
  AuthRouter,
  useAuth,
} from "./AuthProvider";

const approvedProfile: Profile = {
  id: "user-1",
  email: "user@example.com",
  name: "User",
  role: "user",
  status: "approved",
};

function createClient(
  me: ApiClient["auth"]["me"],
): ApiClient {
  return {
    auth: {
      me,
      login: vi.fn(),
      signup: vi.fn(),
      logout: vi.fn().mockResolvedValue({ message: "Logged out." }),
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
  };
}

function renderRouter(client: ApiClient) {
  return render(
    <AuthProvider client={client}>
      {() => (
        <AuthRouter
          publicView={<div data-testid="public">Login</div>}
          authenticatedView={(profile) => (
            <div data-testid="authenticated">{profile.name}</div>
          )}
          blockedView={(message) => (
            <div data-testid="blocked">{message}</div>
          )}
        />
      )}
    </AuthProvider>,
  );
}

describe("AuthProvider", () => {
  it("keeps one stable loading shell before /me resolves", async () => {
    let resolveProfile!: (profile: Profile) => void;
    const me = vi.fn(
      () =>
        new Promise<Profile>((resolve) => {
          resolveProfile = resolve;
        }),
    );
    const client = createClient(me);

    renderRouter(client);

    expect(screen.getByRole("status")).toHaveTextContent(
      "Carregando sessão...",
    );
    expect(screen.queryByTestId("public")).not.toBeInTheDocument();
    expect(screen.queryByTestId("authenticated")).not.toBeInTheDocument();

    resolveProfile(approvedProfile);
    await waitFor(() =>
      expect(screen.getByTestId("authenticated")).toHaveTextContent("User"),
    );
  });

  it("renders the authenticated branch for an approved profile", async () => {
    const client = createClient(
      vi.fn().mockResolvedValue(approvedProfile),
    );

    renderRouter(client);

    await waitFor(() =>
      expect(screen.getByTestId("authenticated")).toBeInTheDocument(),
    );
    expect(screen.queryByTestId("public")).not.toBeInTheDocument();
    expect(screen.queryByTestId("blocked")).not.toBeInTheDocument();
  });

  it("loads an approved session when StrictMode re-runs the effect", async () => {
    const me = vi.fn().mockResolvedValue(approvedProfile);
    const client = createClient(me);

    render(
      <StrictMode>
        <AuthProvider client={client}>
          {() => (
            <AuthRouter
              publicView={<div data-testid="public">Login</div>}
              authenticatedView={(profile) => (
                <div data-testid="authenticated">{profile.name}</div>
              )}
              blockedView={(message) => (
                <div data-testid="blocked">{message}</div>
              )}
            />
          )}
        </AuthProvider>
      </StrictMode>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("authenticated")).toHaveTextContent("User"),
    );
    expect(me).toHaveBeenCalledOnce();
  });

  it("renders the public branch for an unauthenticated response", async () => {
    const client = createClient(
      vi.fn().mockRejectedValue(
        new ApiError("auth_required", "Authentication required.", 401),
      ),
    );

    renderRouter(client);

    await waitFor(() =>
      expect(screen.getByTestId("public")).toBeInTheDocument(),
    );
    expect(screen.queryByTestId("authenticated")).not.toBeInTheDocument();
  });

  it.each([
    ["pending", "Sua conta aguarda aprovação."],
    ["rejected", "Sua solicitação de acesso foi rejeitada."],
    ["disabled", "Sua conta está desativada."],
  ])("blocks %s profiles from chat", async (_status, message) => {
    const client = createClient(
      vi.fn().mockRejectedValue(
        new ApiError(
          "account_not_approved",
          message,
          403,
        ),
      ),
    );

    renderRouter(client);

    await waitFor(() =>
      expect(screen.getByTestId("blocked")).toHaveTextContent(
        message,
      ),
    );
    expect(screen.queryByTestId("authenticated")).not.toBeInTheDocument();
  });

  it("moves to public state on a later 401 and keeps only in-memory draft text", async () => {
    const login = vi
      .fn()
      .mockRejectedValue(
        new ApiError("auth_required", "Authentication required.", 401),
      );
    const client = createClient(
      vi.fn().mockResolvedValue(approvedProfile),
    );
    client.auth.login = login;

    function Harness() {
      const auth = useAuth();
      return (
        <>
          <AuthRouter
            publicView={<div data-testid="public">Login</div>}
            authenticatedView={() => (
              <div data-testid="authenticated">Chat</div>
            )}
            blockedView={(message) => (
              <div data-testid="blocked">{message}</div>
            )}
          />
          <output data-testid="draft">{auth.unsentText}</output>
          <button
            onClick={() => {
              auth.setUnsentText("draft kept in memory");
              void auth.login({
                email: "user@example.com",
                password: "password",
              }).catch(() => undefined);
            }}
          >
            expire
          </button>
        </>
      );
    }

    render(
      <AuthProvider client={client}>{() => <Harness />}</AuthProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId("authenticated")).toBeInTheDocument(),
    );

    screen.getByRole("button", { name: "expire" }).click();
    await waitFor(() =>
      expect(screen.getByTestId("public")).toBeInTheDocument(),
    );
    expect(screen.getByTestId("draft")).toHaveTextContent(
      "draft kept in memory",
    );
  });
});
