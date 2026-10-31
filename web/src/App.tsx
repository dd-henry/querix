import {
  AuthProvider,
  AuthRouter,
  type AuthProviderProps,
} from "./app/AuthProvider";

interface AppProps {
  client?: AuthProviderProps["client"];
}

export function App({ client }: AppProps) {
  return (
    <AuthProvider client={client}>
      {() => (
        <AuthRouter
          publicView={
            <main className="app-shell">
              <section className="welcome-card" aria-labelledby="app-title">
                <p className="eyebrow">Ask SQL</p>
                <h1 id="app-title">Entrar para continuar</h1>
              </section>
            </main>
          }
          authenticatedView={(profile) => (
            <main className="app-shell">
              <section className="welcome-card" aria-labelledby="app-title">
                <p className="eyebrow">Ask SQL</p>
                <h1 id="app-title">Converse com seus dados</h1>
                <p>{profile.name}</p>
              </section>
            </main>
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
