import {
  AuthProvider,
  AuthRouter,
  type AuthProviderProps,
} from "./app/AuthProvider";
import { AuthenticatedApp } from "./app/AuthenticatedApp";
import { AuthPage } from "./features/auth/AuthPage";

interface AppProps {
  client?: AuthProviderProps["client"];
}

export function App({ client }: AppProps) {
  return (
    <AuthProvider client={client}>
      {(auth) => (
        <AuthRouter
          publicView={
            <AuthPage />
          }
          authenticatedView={(profile) => (
            <AuthenticatedApp
              profile={profile}
              client={auth.client}
              onSignOut={auth.logout}
            />
          )}
          blockedView={(message) => (
            <main className="app-shell">
              <section className="welcome-card" aria-labelledby="app-title">
                <p className="eyebrow">Ask SQL</p>
                <h1 id="app-title">Acesso pendente</h1>
                <p>{message}</p>
              </section>
            </main>
          )}
        />
      )}
    </AuthProvider>
  );
}
