import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import {
  ApiError,
  createApiClient,
  type ApiClient,
  type LoginInput,
  type Profile,
  type SignupInput,
  type SignupResponse,
} from "../api/client";

export type AuthState =
  | { status: "loading"; unsentText: string }
  | { status: "unauthenticated"; unsentText: string; message?: string }
  | {
      status: "blocked";
      unsentText: string;
      message: string;
      profile?: Profile;
    }
  | { status: "authenticated"; unsentText: string; profile: Profile };

export type AuthContextValue = AuthState & {
  login: (input: LoginInput) => Promise<Profile>;
  signup: (input: SignupInput) => Promise<SignupResponse | undefined>;
  logout: () => Promise<void>;
  setUnsentText: (text: string) => void;
};

export interface AuthProviderProps {
  children: (auth: AuthContextValue) => ReactNode;
  client?: ApiClient;
}

interface AuthRouterProps {
  publicView: ReactNode;
  authenticatedView: (profile: Profile) => ReactNode;
  blockedView: (message: string, profile?: Profile) => ReactNode;
  loadingView?: ReactNode;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

function blockedMessage(error: ApiError): string {
  return error.message || "Sua conta não está aprovada.";
}

export function AuthProvider({
  children,
  client: providedClient,
}: AuthProviderProps) {
  const [state, setState] = useState<AuthState>({
    status: "loading",
    unsentText: "",
  });
  const loadStarted = useRef(false);

  const handleUnauthorized = useCallback(() => {
    setState((current) => ({
      status: "unauthenticated",
      unsentText: current.unsentText,
      message: "Sua sessão expirou. Entre novamente.",
    }));
  }, []);

  const client = useMemo(
    () =>
      providedClient ??
      createApiClient({
        onUnauthorized: handleUnauthorized,
      }),
    [handleUnauthorized, providedClient],
  );

  const setProfile = useCallback((profile: Profile) => {
    if (profile.status !== "approved") {
      setState((current) => ({
        status: "blocked",
        unsentText: current.unsentText,
        message: "Sua conta não está aprovada.",
        profile,
      }));
      return;
    }
    setState({
      status: "authenticated",
      unsentText: "",
      profile,
    });
  }, []);

  useEffect(() => {
    if (loadStarted.current) {
      return;
    }
    loadStarted.current = true;
    let active = true;

    client.auth.me().then(
      (profile) => {
        if (active && profile) {
          setProfile(profile);
        }
      },
      (error: unknown) => {
        if (!active) {
          return;
        }
        if (isApiError(error) && error.code === "account_not_approved") {
          setState((current) => ({
            status: "blocked",
            unsentText: current.unsentText,
            message: blockedMessage(error),
          }));
          return;
        }
        setState((current) => ({
          status: "unauthenticated",
          unsentText: current.unsentText,
          message:
            isApiError(error) && error.status !== 401
              ? error.message
              : undefined,
        }));
      },
    );

    return () => {
      active = false;
    };
  }, [client, setProfile]);

  const login = useCallback(
    async (input: LoginInput) => {
      try {
        const profile = await client.auth.login(input);
        if (!profile) {
          throw new ApiError(
            "invalid_response",
            "The API returned an empty login response.",
            502,
          );
        }
        if (profile.status !== "approved") {
          setState((current) => ({
            status: "blocked",
            unsentText: current.unsentText,
            message: "Sua conta não está aprovada.",
            profile,
          }));
          throw new ApiError(
            "account_not_approved",
            "Sua conta não está aprovada.",
            403,
          );
        }
        setProfile(profile);
        return profile;
      } catch (error: unknown) {
        if (isApiError(error) && error.status === 401) {
          handleUnauthorized();
        } else if (
          isApiError(error) &&
          error.code === "account_not_approved"
        ) {
          setState((current) => ({
            status: "blocked",
            unsentText: current.unsentText,
            message: blockedMessage(error),
          }));
        }
        throw error;
      }
    },
    [client, handleUnauthorized, setProfile],
  );

  const signup = useCallback(
    (input: SignupInput) => client.auth.signup(input),
    [client],
  );

  const logout = useCallback(async () => {
    try {
      await client.auth.logout();
    } finally {
      setState({
        status: "unauthenticated",
        unsentText: "",
      });
    }
  }, [client]);

  const setUnsentText = useCallback((text: string) => {
    setState((current) => ({ ...current, unsentText: text }));
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      ...state,
      login,
      signup,
      logout,
      setUnsentText,
    }),
    [login, logout, setUnsentText, signup, state],
  );

  return (
    <AuthContext.Provider value={value}>
      {children(value)}
    </AuthContext.Provider>
  );
}

// The hook intentionally shares the provider module to keep the auth contract together.
// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error("useAuth must be used inside AuthProvider.");
  }
  return value;
}

export function AuthRouter({
  publicView,
  authenticatedView,
  blockedView,
  loadingView = (
    <main className="app-shell">
      <div role="status" aria-live="polite">
        Carregando sessão...
      </div>
    </main>
  ),
}: AuthRouterProps) {
  const auth = useAuth();
  if (auth.status === "loading") {
    return loadingView;
  }
  if (auth.status === "authenticated") {
    return authenticatedView(auth.profile);
  }
  if (auth.status === "blocked") {
    return blockedView(auth.message, auth.profile);
  }
  return publicView;
}
