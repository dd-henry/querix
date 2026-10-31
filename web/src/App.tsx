import {
  AuthProvider,
  AuthRouter,
  type AuthProviderProps,
} from "./app/AuthProvider";
import { AppShell } from "./app/AppShell";
import { AuthPage } from "./features/auth/AuthPage";
import { ConversationSidebar } from "./features/conversations/ConversationSidebar";

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
            <AppShell
              profile={profile}
              onSignOut={auth.logout}
              sidebar={(closeSidebar) => (
                <>
                  <ConversationSidebar
                    client={auth.client}
                    onCloseMobile={closeSidebar}
                  />
                  <nav aria-label="Seções">
                    <ul>
                      <li>
                        <button type="button">Histórico</button>
                      </li>
                      <li>
                        <button type="button">
                          Consultas compartilhadas
                        </button>
                      </li>
                      {profile.role !== "user" ? (
                        <li>
                          <button type="button">Administração</button>
                        </li>
                      ) : null}
                    </ul>
                  </nav>
                </>
              )}
              chat={<p>O chat será carregado aqui.</p>}
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
