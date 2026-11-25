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

const SUMMARY_PREVIEW_LENGTH = 200;

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

function resolveChartColumn(
  candidate: unknown,
  columns: string[],
): string | null {
  if (typeof candidate !== "string") {
    return null;
  }
  const trimmedCandidate = candidate.trim();
  if (!trimmedCandidate) {
    return null;
  }
  const exactMatch = columns.find((column) => column === trimmedCandidate);
  if (exactMatch) {
    return exactMatch;
  }

  const candidateParts = trimmedCandidate.split(".");
  const leaf = candidateParts[candidateParts.length - 1]?.trim();
  if (!leaf) {
    return null;
  }
  const normalizedLeaf = leaf.toLowerCase();
  const matches = columns.filter((column) => {
    const columnParts = column.split(".");
    const columnLeaf = columnParts[columnParts.length - 1]?.trim().toLowerCase();
    return (
      column.toLowerCase() === normalizedLeaf ||
      columnLeaf === normalizedLeaf
    );
  });
  return matches.length === 1 ? matches[0] : null;
}

function chartNumber(value: unknown): number | null {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }
  if (
    typeof value !== "string" ||
    !/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(value.trim())
  ) {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function inferredChart(result: ResultData): ChartSpec | null {
  if (result.columns.length !== 2 || result.rows.length < 2) {
    return null;
  }
  const numeric = result.columns.filter((column) =>
    result.rows.every((row) => chartNumber(row[column]) !== null),
  );
  const labels = result.columns.filter((column) =>
    result.rows.every(
      (row) =>
        typeof row[column] === "string" &&
        row[column].trim() !== "" &&
        chartNumber(row[column]) === null,
    ),
  );
  if (numeric.length !== 1 || labels.length !== 1) {
    return null;
  }
  if (new Set(result.rows.map((row) => row[labels[0]])).size !== result.rows.length) {
    return null;
  }
  return {
    tipo: "bar",
    eixo_x: labels[0],
    eixo_y: numeric[0],
    titulo: `${numeric[0]} por ${labels[0]}`,
  };
}

function ChartView({
  spec,
  result,
}: {
  spec: ChartSpec;
  result: ResultData;
}) {
  const type = spec.tipo;
  const x = resolveChartColumn(spec.eixo_x, result.columns);
  const y = resolveChartColumn(spec.eixo_y, result.columns);
  if (type !== "bar" && type !== "line") {
    return (
      <p className="chat-result__chart-warning" role="alert">
        Tipo de gráfico não suportado.
      </p>
    );
  }
  if (
    x === null ||
    y === null
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
    data: result.rows.map((row) => ({
      ...row,
      [y]: chartNumber(row[y]),
    })),
    width: 720,
    height: 360,
    margin: { top: 16, right: 24, bottom: 8, left: 8 },
  };
  const axisTick = { fill: "#d1dce9", fontSize: 12 };
  const tooltipProps = {
    contentStyle: {
      backgroundColor: "#0f172a",
      border: "1px solid #64748b",
      borderRadius: "0.5rem",
      boxShadow: "0 8px 24px rgba(0, 0, 0, 0.3)",
    },
    labelStyle: { color: "#f8fafc", fontWeight: 600 },
    itemStyle: { color: "#bfdbfe" },
  };
  const formatTick = (value: unknown) => {
    const text = String(value ?? "");
    return text.length > 18 ? `${text.slice(0, 17)}…` : text;
  };
  return (
    <figure className="chat-result__chart" aria-label={title}>
      <figcaption>{title}</figcaption>
      <div className="chat-result__chart-scroll" tabIndex={0} role="region" aria-label="Gráfico rolável">
        <div className="chat-result__chart-canvas" data-testid={`${type}-chart`}>
          {type === "bar" ? (
            <BarChart {...chartProps}>
              <CartesianGrid stroke="#475569" strokeDasharray="3 4" vertical={false} />
              <XAxis dataKey={x} tick={axisTick} tickLine={false} axisLine={{ stroke: "#64748b" }} angle={-30} textAnchor="end" height={90} tickFormatter={formatTick} />
              <YAxis tick={axisTick} tickLine={false} axisLine={false} />
              <Tooltip {...tooltipProps} cursor={{ fill: "rgba(148, 163, 184, 0.12)" }} />
              <Bar dataKey={y} fill="#60a5fa" radius={[4, 4, 0, 0]} maxBarSize={52} />
            </BarChart>
          ) : (
            <LineChart {...chartProps}>
              <CartesianGrid stroke="#475569" strokeDasharray="3 4" vertical={false} />
              <XAxis dataKey={x} tick={axisTick} tickLine={false} axisLine={{ stroke: "#64748b" }} angle={-30} textAnchor="end" height={90} tickFormatter={formatTick} />
              <YAxis tick={axisTick} tickLine={false} axisLine={false} />
              <Tooltip {...tooltipProps} cursor={{ stroke: "#94a3b8", strokeDasharray: "3 4" }} />
              <Line type="monotone" dataKey={y} stroke="#60a5fa" strokeWidth={3} dot={{ fill: "#93c5fd", r: 4 }} activeDot={{ r: 6 }} />
            </LineChart>
          )}
        </div>
      </div>
    </figure>
  );
}

function SummaryView({ summary }: { summary: string }) {
  const [expanded, setExpanded] = useState(false);
  if (summary.length <= SUMMARY_PREVIEW_LENGTH) {
    return <p className="chat-result__summary">{summary}</p>;
  }
  const prefix = summary.slice(0, SUMMARY_PREVIEW_LENGTH);
  const boundary = prefix.lastIndexOf(" ");
  const preview = (boundary > 0 ? prefix.slice(0, boundary) : prefix).trimEnd();
  return (
    <div className="chat-result__summary">
      <p>{expanded ? summary : `${preview}…`}</p>
      <button
        type="button"
        aria-expanded={expanded}
        onClick={() => setExpanded((current) => !current)}
      >
        {expanded ? "Mostrar menos" : "Ler resumo completo"}
      </button>
    </div>
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
        <SummaryView summary={message.summary} />
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
        <table className="chat-result__table">
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
      role="region"
    >
      <details className="chat-collapsible">
        <summary className="chat-collapsible__summary" role="button">
          <span className="chat-collapsible__label">
            <span className="chat-collapsible__title">
              Como entendi sua pergunta
            </span>
            <span className="chat-collapsible__summary-text">
              {interpretation.intent}
            </span>
          </span>
          <span className="chat-collapsible__hint">Ver detalhes</span>
        </summary>
        <div className="chat-collapsible__content">
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
        </div>
      </details>
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
              <table className="chat-result__table">
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
      <details className="chat-collapsible" role="region">
        <summary className="chat-collapsible__summary" role="button">
          <span className="chat-collapsible__title">Leitura gerencial</span>
          <span className="chat-collapsible__hint">
            Indicadores complementares para contextualizar a resposta
          </span>
        </summary>
        <div className="chat-collapsible__content">
          {message.insights.map((insight, index) => (
            <InsightView
              key={insight.key}
              insight={insight}
              requestId={message.requestId}
              index={index}
            />
          ))}
        </div>
      </details>
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
          const spec = message.result
            ? chartSpec(message) ?? inferredChart(message.result)
            : null;

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
                  {spec && message.result ? (
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
                          spec={spec}
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
