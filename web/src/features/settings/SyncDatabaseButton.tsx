import { useState } from "react";

import { ApiError, type ApiClient } from "../../api/client";

export interface SyncDatabaseButtonProps {
  client: ApiClient;
  onSynced?: () => void;
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "Não foi possível sincronizar o banco.";
}

export function SyncDatabaseButton({
  client,
  onSynced,
}: SyncDatabaseButtonProps) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");

  const handleSync = async () => {
    if (pending) {
      return;
    }
    setPending(true);
    setError("");
    setFeedback("");
    try {
      const response = await client.schema.sync();
      if (response.status !== "synchronized") {
        throw new ApiError(
          "invalid_response",
          "A sincronização retornou um status inválido.",
          502,
        );
      }
      setFeedback("Banco sincronizado com sucesso.");
      onSynced?.();
    } catch (syncError: unknown) {
      setError(errorMessage(syncError));
    } finally {
      setPending(false);
    }
  };

  return (
    <section className="sync-panel" aria-labelledby="sync-panel-title">
      <div>
        <p className="eyebrow">Schema</p>
        <h2 id="sync-panel-title">Sincronizar banco</h2>
        <p>
          Atualize o contexto do tradutor e o catálogo depois de alterar o
          schema.
        </p>
      </div>
      <button type="button" onClick={() => void handleSync()} disabled={pending}>
        {pending ? "Sincronizando..." : "Sincronizar Banco"}
      </button>
      {error ? <p role="alert">{error}</p> : null}
      {feedback ? <p role="status">{feedback}</p> : null}
    </section>
  );
}
