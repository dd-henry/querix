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

import type { ChatInsight } from "../../api/client";
import type { ChatDiagnostics, ChatInterpretation } from "../../api/client";
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
  onCancelRequest?: () => boolean;
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
      {message.summary ? (
        <p className="chat-result__summary">{message.summary}</p>
      ) : null}
      {message.sql ? (
        <details className="chat-result__sql">
          <summary>Ver SQL executado</summary>
          <pre>{message.sql}</pre>
        </details>
      ) : null}
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

function listValue(values: string[]): string {
  return values.length > 0 ? values.join(", ") : "Nenhuma informada";
}

function periodValue(period: ChatInterpretation["period"]): string {
  if (!period) {
    return "Nenhum período definido";
  }
  const label = typeof period.label === "string" ? period.label : "";
  const start = typeof period.start === "string" ? period.start : "";
  const end = typeof period.end === "string" ? period.end : "";
  const interval = start && end ? `${start} até ${end}` : "";
  return [label, interval].filter(Boolean).join(" — ") || "Período interpretado";
}

function InterpretationView({
  interpretation,
}: {
  interpretation: ChatInterpretation;
}) {
  return (
    <section
      className="chat-interpretation"
      aria-label="Interpretação da pergunta"
    >
      <h2>Como entendi sua pergunta</h2>
      <p className="chat-interpretation__intent">{interpretation.intent}</p>
      <dl>
        <div>
          <dt>Dimensões</dt>
          <dd>{listValue(interpretation.dimensions)}</dd>
        </div>
        <div>
          <dt>Métricas</dt>
          <dd>{listValue(interpretation.metrics)}</dd>
        </div>
        <div>
          <dt>Período</dt>
          <dd>{periodValue(interpretation.period)}</dd>
        </div>
      </dl>
      {interpretation.assumptions.length > 0 ? (
        <div>
          <h3>Premissas</h3>
          <ul>
            {interpretation.assumptions.map((assumption) => (
              <li key={assumption}>{assumption}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

function DiagnosticsView({
  diagnostics,
}: {
  diagnostics: ChatDiagnostics;
}) {
  return (
    <section
      className="chat-diagnostics"
      aria-label="Diagnóstico do resultado"
    >
      <h3>Sobre este resultado</h3>
      <p>{diagnostics.message}</p>
      {diagnostics.expected_columns.length > 0 ? (
        <p>
          Colunas esperadas: {diagnostics.expected_columns.join(", ")}.
        </p>
      ) : null}
    </section>
  );
}

function InsightView({
  insight,
  requestId,
  index,
}: {
  insight: ChatInsight;
  requestId: string;
  index: number;
}) {
  const result = insight.result;
  return (
    <article className="chat-insight">
      <div className="chat-insight__header">
        <h3>{insight.title}</h3>
        {result ? <span>{result.row_count} linha(s)</span> : null}
      </div>
      {insight.summary ? (
        <p className="chat-insight__summary">{insight.summary}</p>
      ) : null}
      {insight.warning ? (
        <p className="chat-insight__warning" role="alert">
          {insight.warning}
        </p>
      ) : null}
      {insight.sql ? (
        <details className="chat-result__sql">
          <summary>Ver SQL da análise</summary>
          <pre>{insight.sql}</pre>
        </details>
      ) : null}
      {result ? (
        <>
          {result.truncated ? (
            <p className="chat-result__notice">
              Os resultados foram limitados às primeiras 5.000 linhas.
            </p>
          ) : null}
          {result.columns.length > 0 ? (
            <div className="chat-result__table-wrapper">
              <table>
                <caption className="sr-only">
                  Resultado da análise {insight.title}
                </caption>
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
                    <tr key={`${requestId}-${insight.key}-${rowIndex}`}>
                      {result.columns.map((column) => (
                        <td key={column}>{String(row[column] ?? "")}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
          <a
            className="chat-result__download"
            download={`analise-${requestId}-${index + 1}.csv`}
            href={`data:text/csv;charset=utf-8,${encodeURIComponent(
              resultCsv(result),
            )}`}
          >
            Download Análise (CSV)
          </a>
        </>
      ) : null}
    </article>
  );
}

function InsightsView({
  message,
}: {
  message: ChatMessage;
}) {
  if (!message.insights || message.insights.length === 0) {
    return null;
  }
  return (
    <section className="chat-insights" aria-label="Leitura gerencial">
      <div className="chat-insights__header">
        <h2>Leitura gerencial</h2>
        <span>Indicadores complementares para contextualizar a resposta</span>
      </div>
      {message.insights.map((insight, index) => (
        <InsightView
          key={insight.key}
          insight={insight}
          requestId={message.requestId}
          index={index}
        />
      ))}
    </section>
  );
}

export function ChatWorkspace({
  messages,
  error,
  onSend,
  onCancelRequest,
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
    const promptToSend = prompt;
    setPrompt("");
    await onSend(promptToSend);
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
        onCancelRequest={onCancelRequest}
        onRetry={(requestId) => {
          void onRetry(requestId);
        }}
        renderAfterMessage={(message) => {
          if (message.role !== "assistant") {
            return null;
          }

          const showReexecution =
            Boolean(message.reexecuteAvailable) &&
            Boolean(message.sql) &&
            !message.result &&
            message.status !== "pending" &&
            message.status !== "error";
          const showReview = message.reviewState === "open" && message.sql;

          return (
            <>
              {message.interpretation ? (
                <InterpretationView interpretation={message.interpretation} />
              ) : null}
              {showReview || showReexecution ? (
                <section
                  className="chat-review"
                  aria-label={
                    showReview ? "Revisão de SQL" : "Reexecução da consulta"
                  }
                >
                  <h2>
                    {showReview
                      ? "SQL aguardando revisão"
                      : "Consulta pronta para reexecução"}
                  </h2>
                  <pre>{message.sql}</pre>
                  <div className="chat-review__actions">
                    <button
                      type="button"
                      disabled={Boolean(pendingRequestId)}
                      onClick={() =>
                        void onConfirmExecution(message.requestId)
                      }
                    >
                      {showReview
                        ? "Executar SQL revisado"
                        : "Reexecutar consulta"}
                    </button>
                    {showReview ? (
                      <button
                        type="button"
                        disabled={Boolean(pendingRequestId)}
                        onClick={() => onCancelReview(message.requestId)}
                      >
                        Cancelar revisão
                      </button>
                    ) : null}
                  </div>
                </section>
              ) : null}
              {message.result || message.diagnostics ? (
                <section
                  className="chat-result-actions"
                  aria-label="Ações do resultado"
                >
                  {message.diagnostics ? (
                    <DiagnosticsView diagnostics={message.diagnostics} />
                  ) : null}
                  {message.chart && message.result ? (
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
                  {message.result ? <ResultView message={message} /> : null}
                </section>
              ) : null}
              <InsightsView message={message} />
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
