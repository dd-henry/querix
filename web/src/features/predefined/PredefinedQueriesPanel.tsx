import { useCallback, useEffect, useState, type FormEvent } from "react";

import {
  ApiError,
  type ApiClient,
  type PredefinedParameter,
  type PredefinedQuery,
  type PredefinedWriteInput,
  type PredefinedExecutionResponse,
  type UserRole,
} from "../../api/client";

export interface PredefinedQueriesPanelProps {
  client: ApiClient;
  role: UserRole;
  onExecutionResult: (response: PredefinedExecutionResponse) => void;
}

interface EditorState {
  id?: number;
  name: string;
  description: string;
  sql: string;
  tags: string;
  parameters: string;
}

function messageFor(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return fallback;
}

function emptyEditor(): EditorState {
  return {
    name: "",
    description: "",
    sql: "",
    tags: "",
    parameters: "[]",
  };
}

function editorFromQuery(query: PredefinedQuery): EditorState {
  return {
    id: query.id,
    name: query.name,
    description: query.description,
    sql: query.sql,
    tags: query.tags.join(", "),
    parameters: JSON.stringify(query.parameters, null, 2),
  };
}

function parametersForRequest(value: string): Array<Record<string, unknown>> {
  const parsed: unknown = JSON.parse(value);
  if (!Array.isArray(parsed)) {
    throw new Error("Parâmetros devem ser uma lista JSON.");
  }
  if (
    !parsed.every(
      (item) => item !== null && typeof item === "object" && !Array.isArray(item),
    )
  ) {
    throw new Error("Cada parâmetro deve ser um objeto JSON.");
  }
  return parsed as Array<Record<string, unknown>>;
}

export function PredefinedQueriesPanel({
  client,
  role,
  onExecutionResult,
}: PredefinedQueriesPanelProps) {
  const [queries, setQueries] = useState<PredefinedQuery[]>([]);
  const [search, setSearch] = useState("");
  const [activeSearch, setActiveSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [parameterQueryId, setParameterQueryId] = useState<number | null>(null);
  const [parameterValues, setParameterValues] = useState<
    Record<string, string>
  >({});
  const [parameterError, setParameterError] = useState("");
  const [editor, setEditor] = useState<EditorState | null>(null);
  const [deleteQueryId, setDeleteQueryId] = useState<number | null>(null);
  const canManage = role === "dev" || role === "dba" || role === "admin";

  const loadQueries = useCallback(
    async (searchTerm: string) => {
      setLoading(true);
      setError("");
      try {
        const response = await client.predefined.list(searchTerm);
        setQueries(response.queries);
      } catch (loadError: unknown) {
        setError(messageFor(loadError, "Não foi possível carregar as consultas."));
      } finally {
        setLoading(false);
      }
    },
    [client],
  );

  useEffect(() => {
    void loadQueries("");
  }, [loadQueries]);

  const handleSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextSearch = search.trim();
    setActiveSearch(nextSearch);
    void loadQueries(nextSearch);
  };

  const handleFavorite = async (query: PredefinedQuery) => {
    setPendingAction(`favorite:${query.id}`);
    setError("");
    try {
      const response = await client.predefined.favorite(
        query.id,
        !query.is_favorite,
      );
      setQueries((current) =>
        current.map((item) =>
          item.id === query.id
            ? { ...item, is_favorite: response.is_favorite }
            : item,
        ),
      );
    } catch (favoriteError: unknown) {
      setError(messageFor(favoriteError, "Não foi possível atualizar o favorito."));
    } finally {
      setPendingAction(null);
    }
  };

  const openParameters = (query: PredefinedQuery) => {
    setParameterQueryId(query.id);
    setParameterError("");
    setParameterValues({});
  };

  const handleExecute = async (query: PredefinedQuery) => {
    const values: Record<string, unknown> = { ...parameterValues };
    const missing = query.parameters.find(
      (parameter) =>
        parameter.required &&
        (!values[parameter.name] || String(values[parameter.name]).trim() === ""),
    );
    if (missing) {
      setParameterError(
        `Informe o parâmetro ${missing.label || missing.name}.`,
      );
      return;
    }
    setPendingAction(`execute:${query.id}`);
    setParameterError("");
    setError("");
    try {
      const response = await client.predefined.execute(query.id, values);
      onExecutionResult(response);
      setFeedback("Consulta compartilhada executada.");
      setParameterQueryId(null);
    } catch (executionError: unknown) {
      setError(messageFor(executionError, "Não foi possível executar a consulta."));
    } finally {
      setPendingAction(null);
    }
  };

  const handleEditorSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!editor) {
      return;
    }
    if (!editor.name.trim() || !editor.sql.trim()) {
      setError("Informe nome e SQL para salvar a consulta.");
      return;
    }
    let parameters: Array<Record<string, unknown>>;
    try {
      parameters = parametersForRequest(editor.parameters);
    } catch (parseError: unknown) {
      setError(messageFor(parseError, "Os parâmetros devem ser um JSON válido."));
      return;
    }
    const payload: PredefinedWriteInput = {
      name: editor.name.trim(),
      description: editor.description.trim(),
      sql: editor.sql.trim(),
      tags: editor.tags
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean),
      parameters,
    };
    setPendingAction("save");
    setError("");
    try {
      if (editor.id === undefined) {
        await client.predefined.create(payload);
        setFeedback("Consulta compartilhada criada.");
      } else {
        await client.predefined.update(editor.id, payload);
        setFeedback("Consulta compartilhada atualizada.");
      }
      setEditor(null);
      await loadQueries(activeSearch);
    } catch (saveError: unknown) {
      setError(messageFor(saveError, "Não foi possível salvar a consulta."));
    } finally {
      setPendingAction(null);
    }
  };

  const handleDelete = async (queryId: number) => {
    setPendingAction(`delete:${queryId}`);
    setError("");
    try {
      await client.predefined.delete(queryId);
      setQueries((current) => current.filter((query) => query.id !== queryId));
      setDeleteQueryId(null);
      setFeedback("Consulta compartilhada excluída.");
    } catch (deleteError: unknown) {
      setError(messageFor(deleteError, "Não foi possível excluir a consulta."));
    } finally {
      setPendingAction(null);
    }
  };

  return (
    <section
      className="predefined-panel"
      aria-labelledby="predefined-panel-title"
    >
      <header className="predefined-panel__header">
        <div>
          <p className="eyebrow">Catálogo</p>
          <h2 id="predefined-panel-title">Consultas compartilhadas</h2>
        </div>
        {canManage ? (
          <button type="button" onClick={() => setEditor(emptyEditor())}>
            Nova consulta
          </button>
        ) : null}
      </header>
      <form className="predefined-panel__search" onSubmit={handleSearch}>
        <label htmlFor="predefined-search">Buscar consulta</label>
        <input
          id="predefined-search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          type="search"
        />
        <button type="submit" disabled={loading}>
          Buscar
        </button>
      </form>
      {error ? <p role="alert">{error}</p> : null}
      {feedback ? <p role="status">{feedback}</p> : null}
      {editor ? (
        <form className="predefined-editor" onSubmit={(event) => void handleEditorSubmit(event)}>
          <h3>{editor.id === undefined ? "Nova consulta" : "Editar consulta"}</h3>
          <label htmlFor="predefined-name">Nome</label>
          <input
            id="predefined-name"
            value={editor.name}
            onChange={(event) => setEditor({ ...editor, name: event.target.value })}
          />
          <label htmlFor="predefined-description">Descrição</label>
          <input
            id="predefined-description"
            value={editor.description}
            onChange={(event) =>
              setEditor({ ...editor, description: event.target.value })
            }
          />
          <label htmlFor="predefined-sql">SQL somente leitura</label>
          <textarea
            id="predefined-sql"
            value={editor.sql}
            onChange={(event) => setEditor({ ...editor, sql: event.target.value })}
            rows={4}
          />
          <label htmlFor="predefined-tags">Tags separadas por vírgula</label>
          <input
            id="predefined-tags"
            value={editor.tags}
            onChange={(event) => setEditor({ ...editor, tags: event.target.value })}
          />
          <label htmlFor="predefined-parameters">Parâmetros em JSON</label>
          <textarea
            id="predefined-parameters"
            value={editor.parameters}
            onChange={(event) =>
              setEditor({ ...editor, parameters: event.target.value })
            }
            rows={4}
          />
          <button type="submit" disabled={pendingAction === "save"}>
            Salvar consulta
          </button>
          <button type="button" onClick={() => setEditor(null)}>
            Cancelar
          </button>
        </form>
      ) : null}
      {loading ? (
        <p role="status">Carregando consultas...</p>
      ) : queries.length === 0 ? (
        <p role="status">Nenhuma consulta encontrada.</p>
      ) : (
        <ul className="predefined-panel__list">
          {queries.map((query) => {
            const actionPending =
              pendingAction === `favorite:${query.id}` ||
              pendingAction === `execute:${query.id}` ||
              pendingAction === `delete:${query.id}`;
            const hasParameters = query.parameters.length > 0;
            return (
              <li key={query.id} className="predefined-panel__item">
                <h3>{query.name}</h3>
                <p>{query.description}</p>
                <pre>{query.sql}</pre>
                <p>{query.tags.join(", ")}</p>
                <button
                  type="button"
                  disabled={actionPending}
                  onClick={() => void handleFavorite(query)}
                >
                  {query.is_favorite ? "Desfavoritar" : "Favoritar"}
                </button>
                {canManage ? (
                  <>
                    <button type="button" onClick={() => setEditor(editorFromQuery(query))}>
                      Editar
                    </button>
                    <button
                      type="button"
                      disabled={actionPending}
                      onClick={() => setDeleteQueryId(query.id)}
                    >
                      Excluir
                    </button>
                  </>
                ) : null}
                <button
                  type="button"
                  disabled={actionPending}
                  onClick={() =>
                    hasParameters
                      ? openParameters(query)
                      : void handleExecute(query)
                  }
                >
                  Executar
                </button>
                {parameterQueryId === query.id ? (
                  <div className="predefined-parameters">
                    <h4>Parâmetros</h4>
                    {query.parameters.map((parameter: PredefinedParameter) => (
                      <label key={parameter.name} htmlFor={`parameter-${query.id}-${parameter.name}`}>
                        {parameter.label || parameter.name}
                        {parameter.required ? " *" : ""}
                        <input
                          id={`parameter-${query.id}-${parameter.name}`}
                          value={parameterValues[parameter.name] ?? ""}
                          onChange={(event) =>
                            setParameterValues({
                              ...parameterValues,
                              [parameter.name]: event.target.value,
                            })
                          }
                        />
                      </label>
                    ))}
                    {parameterError ? <p role="alert">{parameterError}</p> : null}
                    <button
                      type="button"
                      disabled={actionPending}
                      onClick={() => void handleExecute(query)}
                    >
                      Executar consulta
                    </button>
                    <button type="button" onClick={() => setParameterQueryId(null)}>
                      Cancelar
                    </button>
                  </div>
                ) : null}
                {deleteQueryId === query.id ? (
                  <div role="group" aria-label={`Confirmar exclusão de ${query.name}`}>
                    <span>Excluir esta consulta?</span>
                    <button
                      type="button"
                      disabled={actionPending}
                      onClick={() => void handleDelete(query.id)}
                    >
                      Confirmar exclusão
                    </button>
                    <button type="button" onClick={() => setDeleteQueryId(null)}>
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
