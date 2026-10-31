import { useMemo, useState, type FormEvent, type KeyboardEvent } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { ChatMessage } from "./useChat";
import { MessageList } from "./MessageList";

interface ChartSpec {
  tipo?: unknown;
  eixo_x?: unknown;
  eixo_y?: unknown;
  titulo?: unknown;
}

interface ResultData {
  columns: string[];
  rows: Array<Record<string, unknown>>;
  row_count: number;
  truncated: boolean;
}

export interface ChatWorkspaceProps {
  messages: ChatMessage[];
  error?: string | null;
  onSend: (prompt: string) => Promise<boolean>;
  onRetry: (requestId: string) => Promise<boolean>;
  onConfirmExecution: (requestId: string) => Promise<boolean>;
  onCancelReview: (requestId: string) => void;
}

function csvValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "";
  }
  const text =
    typeof value === "string" ? value : JSON.stringify(value) ?? String(value);
  return `"${text.replace(/"/g, '""')}"`;
}

function resultCsv(result: ResultData): string {
  const rows = [
    result.columns,
    ...result.rows.map((row) =>
      result.columns.map((column) => row[column]),
    ),
  ];
  return `\uFEFF${rows
    .map((row) => row.map((value) => csvValue(value)).join(","))
    .join("\r\n")}`;
}

function chartSpec(message: ChatMessage): ChartSpec | null {
  if (!message.chart || typeof message.chart !== "object") {
    return null;
  }
  return message.chart as ChartSpec;
}

function ChartView({
  message,
  result,
}: {
  message: ChatMessage;
  result: ResultData;
}) {
  const spec = chartSpec(message);
  if (!spec) {
    return null;
  }
  const type = spec.tipo;
  const x = spec.eixo_x;
  const y = spec.eixo_y;
  if (type !== "bar" && type !== "line") {
    return (
      <p className="chat-result__chart-warning" role="alert">
        Tipo de gráfico não suportado.
      </p>
    );
  }
  if (
    typeof x !== "string" ||
    typeof y !== "string" ||
    !result.columns.includes(x) ||
    !result.columns.includes(y)
  ) {
    return (
      <p className="chat-result__chart-warning" role="alert">
        As colunas sugeridas pela IA para o gráfico não existem no resultado.
      </p>
    );
  }

  const title =
    typeof spec.titulo === "string"
      ? spec.titulo
      : "Visualização de dados";
  const chartProps = {
    data: result.rows,
    width: 640,
    height: 280,
  };
  return (
    <figure className="chat-result__chart" aria-label={title}>
      <figcaption>{title}</figcaption>
      {type === "bar" ? (
        <div data-testid="bar-chart">
          <BarChart {...chartProps}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey={x} />
            <YAxis />
            <Tooltip />
            <Bar dataKey={y} fill="#93c5fd" />
          </BarChart>
        </div>
      ) : (
        <div data-testid="line-chart">
          <LineChart {...chartProps}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey={x} />
            <YAxis />
            <Tooltip />
            <Line type="monotone" dataKey={y} stroke="#93c5fd" />
          </LineChart>
        </div>
      )}
    </figure>
  );
}

function ResultView({ message }: { message: ChatMessage }) {
  if (!message.result) {
    return null;
  }
  const result = message.result;
  return (
    <section className="chat-result" aria-label="Resultados da consulta">
      <div className="chat-result__header">
        <h3>Resultados</h3>
        <span>{result.row_count} linha(s)</span>
      </div>
      {result.truncated ? (
        <p className="chat-result__notice">
          Os resultados foram limitados às primeiras 5.000 linhas.
        </p>
      ) : null}
      <div className="chat-result__table-wrapper">
        <table>
          <caption className="sr-only">Linhas retornadas pela consulta</caption>
          <thead>
            <tr>
              {result.columns.map((column) => (
                <th key={column} scope="col">
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {result.rows.map((row, rowIndex) => (
              <tr key={`${message.requestId}-${rowIndex}`}>
                {result.columns.map((column) => (
                  <td key={column}>{String(row[column] ?? "")}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <a
        className="chat-result__download"
        download={`relatorio-${message.requestId}.csv`}
        href={`data:text/csv;charset=utf-8,${encodeURIComponent(
          resultCsv(result),
        )}`}
      >
        Download Relatório (CSV)
      </a>
    </section>
  );
}

export function ChatWorkspace({
  messages,
  error,
  onSend,
  onRetry,
  onConfirmExecution,
  onCancelReview,
}: ChatWorkspaceProps) {
  const [prompt, setPrompt] = useState("");
  const [visibleCharts, setVisibleCharts] = useState<Set<string>>(
    () => new Set(),
  );
  const pendingRequestId = useMemo(
    () =>
      messages.find((message) => message.status === "pending")?.requestId,
    [messages],
  );
  const submitPrompt = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const sent = await onSend(prompt);
    if (sent) {
      setPrompt("");
    }
  };

  const handlePromptKeyDown = (
    event: KeyboardEvent<HTMLTextAreaElement>,
  ) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  };

  const toggleChart = (requestId: string) => {
    setVisibleCharts((current) => {
      const next = new Set(current);
      if (next.has(requestId)) {
        next.delete(requestId);
      } else {
        next.add(requestId);
      }
      return next;
    });
  };

  return (
    <div className="chat-workspace">
      <MessageList
        messages={messages}
        pendingRequestId={pendingRequestId}
        onRetry={(requestId) => {
          void onRetry(requestId);
        }}
        renderAfterMessage={(message) => {
          if (message.role !== "assistant") {
            return null;
          }

          return (
            <>
              {message.reviewState === "open" && message.sql ? (
                <section
                  className="chat-review"
                  aria-label="Revisão de SQL"
                >
                  <h2>SQL aguardando revisão</h2>
                  <pre>{message.sql}</pre>
                  <div className="chat-review__actions">
                    <button
                      type="button"
                      disabled={Boolean(pendingRequestId)}
                      onClick={() =>
                        void onConfirmExecution(message.requestId)
                      }
                    >
                      Executar SQL revisado
                    </button>
                    <button
                      type="button"
                      disabled={Boolean(pendingRequestId)}
                      onClick={() => onCancelReview(message.requestId)}
                    >
                      Cancelar revisão
                    </button>
                  </div>
                </section>
              ) : null}
              {message.result ? (
                <section
                  className="chat-result-actions"
                  aria-label="Ações do resultado"
                >
                  {message.chart ? (
                    <>
                      <button
                        type="button"
                        onClick={() => toggleChart(message.requestId)}
                      >
                        {visibleCharts.has(message.requestId)
                          ? "Ocultar Gráfico"
                          : "Gerar Gráfico"}
                      </button>
                      {visibleCharts.has(message.requestId) ? (
                        <ChartView
                          message={message}
                          result={message.result}
                        />
                      ) : null}
                    </>
                  ) : null}
                  <ResultView message={message} />
                </section>
              ) : null}
            </>
          );
        }}
      />
      {error ? <p role="alert">{error}</p> : null}
      <form className="chat-composer" onSubmit={(event) => void submitPrompt(event)}>
        <label htmlFor="chat-prompt">Pergunte sobre seus dados</label>
        <textarea
          id="chat-prompt"
          value={prompt}
          disabled={Boolean(pendingRequestId)}
          onChange={(event) => setPrompt(event.target.value)}
          onKeyDown={handlePromptKeyDown}
          placeholder="Ex.: Quais foram as vendas deste mês?"
          rows={3}
        />
        <button
          type="submit"
          disabled={Boolean(pendingRequestId) || !prompt.trim()}
        >
          Enviar pergunta
        </button>
      </form>
    </div>
  );
}
