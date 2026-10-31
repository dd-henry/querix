import { useCallback, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  type ApiClient,
  type ChatResponse,
  type HistoryRecord,
} from "../../api/client";

export interface HistoryPanelProps {
  client: ApiClient;
  conversationId?: string;
  onRerunResult: (response: ChatResponse) => void;
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "Não foi possível carregar o histórico.";
}

function sortRecords(records: HistoryRecord[]): HistoryRecord[] {
  return [...records].sort((left, right) => {
    if (left.is_pinned !== right.is_pinned) {
      return left.is_pinned ? -1 : 1;
    }
    return right.created_at.localeCompare(left.created_at);
  });
}

function createRequestId(): string {
  if (typeof crypto === "undefined" || !crypto.randomUUID) {
    throw new Error("O navegador não suporta identificadores de request.");
  }
  return crypto.randomUUID();
}

export function HistoryPanel({
  client,
  conversationId,
  onRerunResult,
}: HistoryPanelProps) {
  const [records, setRecords] = useState<HistoryRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [pendingDeleteId, setPendingDeleteId] = useState<number | null>(null);
  const [rerunMessage, setRerunMessage] = useState("");

  const loadHistory = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await client.history.list();
      setRecords(sortRecords(response.records));
    } catch (loadError: unknown) {
      setError(errorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, [client]);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  const visibleRecords = useMemo(() => sortRecords(records), [records]);

  const handlePin = async (record: HistoryRecord) => {
    setPendingAction(`pin:${record.id}`);
    setError("");
    try {
      const response = await client.history.pin(
        record.id,
        !record.is_pinned,
      );
      setRecords((current) =>
        current.map((item) =>
          item.id === record.id
            ? { ...item, is_pinned: response.is_pinned }
            : item,
        ),
      );
    } catch (pinError: unknown) {
      setError(errorMessage(pinError));
    } finally {
      setPendingAction(null);
    }
  };

  const handleDelete = async (historyId: number) => {
    setPendingAction(`delete:${historyId}`);
    setError("");
    try {
      await client.history.delete(historyId);
      setRecords((current) =>
        current.filter((record) => record.id !== historyId),
      );
      setPendingDeleteId(null);
    } catch (deleteError: unknown) {
      setError(errorMessage(deleteError));
    } finally {
      setPendingAction(null);
    }
  };

  const handleRerun = async (record: HistoryRecord) => {
    if (!conversationId) {
      setError("Abra uma conversa antes de repetir uma consulta.");
      return;
    }
    setPendingAction(`rerun:${record.id}`);
    setError("");
    setRerunMessage("");
    try {
      const response = await client.history.rerun(record.id, {
        conversation_id: conversationId,
        request_id: createRequestId(),
      });
      onRerunResult(response);
      setRerunMessage("Consulta enviada para a conversa.");
    } catch (rerunError: unknown) {
      setError(errorMessage(rerunError));
    } finally {
      setPendingAction(null);
    }
  };

  return (
    <section className="history-panel" aria-labelledby="history-panel-title">
      <header className="history-panel__header">
        <div>
          <p className="eyebrow">Consultas salvas</p>
          <h2 id="history-panel-title">Histórico</h2>
        </div>
        <button type="button" onClick={() => void loadHistory()} disabled={loading}>
          Atualizar
        </button>
      </header>
      {error ? (
        <div role="alert">
          <p>{error}</p>
          <button type="button" onClick={() => void loadHistory()}>
            Tentar novamente
          </button>
        </div>
      ) : null}
      {rerunMessage ? <p role="status">{rerunMessage}</p> : null}
      {loading ? (
        <p role="status">Carregando histórico...</p>
      ) : visibleRecords.length === 0 ? (
        <p role="status">Nenhuma consulta salva.</p>
      ) : (
        <ul className="history-panel__list">
          {visibleRecords.map((record) => {
            const actionPending =
              pendingAction === `pin:${record.id}` ||
              pendingAction === `delete:${record.id}` ||
              pendingAction === `rerun:${record.id}`;
            return (
              <li key={record.id} className="history-panel__item">
                <div>
                  <h3>{record.prompt}</h3>
                  <p>{record.source === "chat" ? "Chat" : "Consulta compartilhada"}</p>
                  <pre>{record.sql}</pre>
                </div>
                <div className="history-panel__actions">
                  <button
                    type="button"
                    disabled={actionPending}
                    onClick={() => void handlePin(record)}
                  >
                    {record.is_pinned ? "Desafixar" : "Fixar"}
                  </button>
                  <button
                    type="button"
                    disabled={actionPending}
                    onClick={() => setPendingDeleteId(record.id)}
                  >
                    Excluir
                  </button>
                  <button
                    type="button"
                    disabled={actionPending || !conversationId}
                    onClick={() => void handleRerun(record)}
                  >
                    Reexecutar
                  </button>
                </div>
                {pendingDeleteId === record.id ? (
                  <div
                    className="history-panel__confirmation"
                    role="group"
                    aria-label={`Confirmar exclusão de ${record.prompt}`}
                  >
                    <span>Excluir esta consulta do histórico?</span>
                    <button
                      type="button"
                      disabled={pendingAction === `delete:${record.id}`}
                      onClick={() => void handleDelete(record.id)}
                    >
                      Confirmar exclusão
                    </button>
                    <button
                      type="button"
                      onClick={() => setPendingDeleteId(null)}
                    >
                      Cancelar
                    </button>
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
