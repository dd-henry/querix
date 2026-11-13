import { useEffect, useState, type FormEvent } from "react";

import { ApiError, type ApiClient } from "../../api/client";

export interface DatabaseConnectionSettingsProps {
  client: Pick<ApiClient, "settings">;
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "Não foi possível configurar a conexão com o banco.";
}

export function DatabaseConnectionSettings({
  client,
}: DatabaseConnectionSettingsProps) {
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [connectionString, setConnectionString] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");

  useEffect(() => {
    let active = true;
    void client.settings.database
      .get()
      .then((status) => {
        if (active) {
          setConfigured(status.configured);
        }
      })
      .catch((statusError: unknown) => {
        if (active) {
          setError(errorMessage(statusError));
        }
      });
    return () => {
      active = false;
    };
  }, [client]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) {
      return;
    }
    const normalized = connectionString.trim();
    if (!normalized) {
      setError("Informe uma connection string PostgreSQL.");
      setFeedback("");
      return;
    }

    setPending(true);
    setError("");
    setFeedback("");
    try {
      const status = await client.settings.database.save(normalized);
      setConfigured(status.configured);
      setConnectionString("");
      setFeedback("Conexão com o banco configurada com sucesso.");
    } catch (saveError: unknown) {
      setError(errorMessage(saveError));
    } finally {
      setPending(false);
    }
  }

  return (
    <section
      className="database-connection-panel"
      aria-labelledby="database-connection-title"
    >
      <div>
        <p className="eyebrow">Banco de dados</p>
        <h2 id="database-connection-title">Conexão consultada pelo Ask SQL</h2>
        <p>
          Informe uma connection string PostgreSQL. Ela será testada antes de
          ser salva e nunca será exibida novamente.
        </p>
        <p className="database-connection-panel__status" role="status">
          {configured === null
            ? "Verificando configuração..."
            : configured
              ? "Uma conexão global está configurada."
              : "Nenhuma conexão global está configurada."}
        </p>
      </div>
      <form
        className="database-connection-form"
        onSubmit={(event) => void handleSubmit(event)}
      >
        <label htmlFor="database-connection-string">
          Connection string PostgreSQL
        </label>
        <input
          id="database-connection-string"
          name="connection_string"
          type="password"
          autoComplete="new-password"
          placeholder="postgresql://usuario:senha@host:5432/banco"
          value={connectionString}
          onChange={(event) => setConnectionString(event.target.value)}
          disabled={pending}
        />
        <button type="submit" disabled={pending}>
          {pending ? "Testando conexão..." : "Testar e salvar conexão"}
        </button>
      </form>
      {error ? <p role="alert">{error}</p> : null}
      {feedback ? <p role="status">{feedback}</p> : null}
    </section>
  );
}
