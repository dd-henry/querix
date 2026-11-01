import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ChatMessage } from "./useChat";
import { ChatWorkspace } from "./ChatWorkspace";

const userMessage: ChatMessage = {
  requestId: "request-1",
  role: "user",
  content: "Show revenue",
  warnings: [],
};

const reviewMessage: ChatMessage = {
  requestId: "request-1",
  role: "assistant",
  content: "SQL gerado para revisão.",
  status: "review",
  sql: "SELECT month, total FROM sales",
  reviewState: "open",
  warnings: [],
};

const executedMessage: ChatMessage = {
  ...reviewMessage,
  status: "executed",
  reviewState: "confirmed",
  content: "Aqui estão os resultados da consulta:",
  summary: "O resultado reúne 5.001 linhas.",
  chart: {
    tipo: "bar",
    eixo_x: "month",
    eixo_y: "total",
    titulo: "Vendas por mês",
  },
  result: {
    columns: ["month", "total"],
    rows: [
      { month: "Jan", total: 10 },
      { month: "Feb", total: 12 },
    ],
    row_count: 5_001,
    truncated: true,
  },
};

function renderWorkspace(
  messages: ChatMessage[] = [],
  overrides: Partial<React.ComponentProps<typeof ChatWorkspace>> = {},
) {
  const props: React.ComponentProps<typeof ChatWorkspace> = {
    messages,
    onSend: vi.fn().mockResolvedValue(true),
    onRetry: vi.fn().mockResolvedValue(true),
    onConfirmExecution: vi.fn().mockResolvedValue(true),
    onCancelReview: vi.fn(),
    ...overrides,
  };
  return render(<ChatWorkspace {...props} />);
}

describe("ChatWorkspace", () => {
  it("submits on Enter, preserves Shift+Enter, and labels the composer", async () => {
    const onSend = vi.fn().mockResolvedValue(true);
    renderWorkspace([], { onSend });
    const composer = screen.getByLabelText("Pergunte sobre seus dados");

    fireEvent.change(composer, { target: { value: "Show revenue" } });
    fireEvent.keyDown(composer, { key: "Enter" });
    await waitFor(() => expect(onSend).toHaveBeenCalledWith("Show revenue"));

    onSend.mockClear();
    fireEvent.change(composer, { target: { value: "line 1" } });
    fireEvent.keyDown(composer, { key: "Enter", shiftKey: true });
    fireEvent.change(composer, { target: { value: "line 1\nline 2" } });

    expect(onSend).not.toHaveBeenCalled();
    expect(composer).toHaveValue("line 1\nline 2");
    expect(screen.getByRole("button", { name: "Enviar pergunta" })).toHaveAttribute(
      "type",
      "submit",
    );
  });

  it("disables the composer while a request is pending", () => {
    renderWorkspace([
      userMessage,
      {
        ...reviewMessage,
        status: "pending",
        reviewState: undefined,
      },
    ]);

    expect(screen.getByLabelText("Pergunte sobre seus dados")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Enviar pergunta" })).toBeDisabled();
  });

  it("requires explicit review confirmation and exposes cancellation", async () => {
    const onConfirmExecution = vi.fn().mockResolvedValue(true);
    const onCancelReview = vi.fn();
    renderWorkspace([userMessage, reviewMessage], {
      onConfirmExecution,
      onCancelReview,
    });

    expect(screen.getByText("SELECT month, total FROM sales")).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Executar SQL revisado" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Cancelar revisão" }));

    await waitFor(() =>
      expect(onConfirmExecution).toHaveBeenCalledWith("request-1"),
    );
    expect(onCancelReview).toHaveBeenCalledWith("request-1");
  });

  it("offers re-execution for restored SQL without showing review controls", async () => {
    const onConfirmExecution = vi.fn().mockResolvedValue(true);
    renderWorkspace([
      userMessage,
      {
        ...reviewMessage,
        status: undefined,
        reviewState: undefined,
        reexecuteAvailable: true,
        content: "Consulta carregada.",
      },
    ], { onConfirmExecution });

    expect(screen.getByText("SELECT month, total FROM sales")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Reexecutar consulta" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Cancelar revisão" }),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Reexecutar consulta" }));

    await waitFor(() =>
      expect(onConfirmExecution).toHaveBeenCalledWith("request-1"),
    );
  });

  it("does not show re-execution for a restored message without SQL", () => {
    const message = {
      ...reviewMessage,
      sql: undefined,
      reexecuteAvailable: true,
    };
    renderWorkspace([userMessage, message]);

    expect(
      screen.queryByRole("button", { name: "Reexecutar consulta" }),
    ).not.toBeInTheDocument();
  });

  it("shows retry instead of re-execution after restored execution fails", () => {
    const message: ChatMessage = {
      ...reviewMessage,
      status: "error",
      reviewState: undefined,
      reexecuteAvailable: true,
      retryable: true,
      retryKind: "execute",
      content: "Banco indisponível.",
      error: "database_unavailable",
    };
    renderWorkspace([userMessage, message]);

    expect(
      screen.getByRole("button", { name: "Tentar novamente" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Reexecutar consulta" }),
    ).not.toBeInTheDocument();
  });

  it("renders bounded results, truncation notice, and UTF-8 CSV download", () => {
    renderWorkspace([userMessage, executedMessage]);

    expect(screen.getByRole("table")).toBeInTheDocument();
    const summary = screen.getByText("O resultado reúne 5.001 linhas.");
    const table = screen.getByRole("table");
    expect(summary.compareDocumentPosition(table)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
    const sqlDetails = screen.getByText("Ver SQL executado").closest("details");
    expect(sqlDetails).toBeInTheDocument();
    expect(sqlDetails).not.toHaveAttribute("open");
    fireEvent.click(screen.getByText("Ver SQL executado"));
    expect(sqlDetails).toHaveAttribute("open");
    expect(
      screen.getByText("SELECT month, total FROM sales"),
    ).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Jan" })).toBeInTheDocument();
    expect(screen.getByText("Os resultados foram limitados às primeiras 5.000 linhas.")).toBeInTheDocument();
    const download = screen.getByRole("link", {
      name: "Download Relatório (CSV)",
    });
    const href = download.getAttribute("href") ?? "";
    expect(decodeURIComponent(href.split(",", 2)[1] ?? "")).toContain(
      "\uFEFF\"month\",\"total\"",
    );
    expect(download).toHaveAttribute("download", "relatorio-request-1.csv");
  });

  it("renders managerial insights after the primary result without another message", () => {
    const message: ChatMessage = {
      ...executedMessage,
      insights: [
        {
          key: "kpi",
          title: "Indicadores do período",
          summary: "A consulta retornou 1 linha(s).",
          sql: "SELECT 2",
          result: {
            columns: ["total"],
            rows: [{ total: 12 }],
            row_count: 1,
            truncated: false,
          },
        },
        {
          key: "payments",
          title: "Formas de pagamento",
          warning: "Não foi possível calcular esta análise complementar.",
        },
      ],
    };
    renderWorkspace([userMessage, message]);

    const primaryTable = screen.getByRole("table", {
      name: "Linhas retornadas pela consulta",
    });
    const insights = screen.getByRole("region", {
      name: "Leitura gerencial",
    });
    expect(primaryTable.compareDocumentPosition(insights)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
    expect(insights).toHaveTextContent("Indicadores do período");
    expect(insights).toHaveTextContent("A consulta retornou 1 linha(s).");
    expect(insights).toHaveTextContent(
      "Não foi possível calcular esta análise complementar.",
    );
    expect(insights).toHaveTextContent("SELECT 2");
    expect(within(insights).getAllByRole("article")).toHaveLength(2);
  });

  it.each(["bar", "line"] as const)(
    "renders a %s chart only after the user requests it",
    (type) => {
      const message: ChatMessage = {
        ...executedMessage,
        chart: { ...executedMessage.chart, tipo: type },
      };
      renderWorkspace([userMessage, message]);

      expect(screen.queryByTestId(`${type}-chart`)).not.toBeInTheDocument();
      fireEvent.click(screen.getByRole("button", { name: "Gerar Gráfico" }));

      expect(screen.getByTestId(`${type}-chart`)).toBeInTheDocument();
    },
  );

  it("shows the required warning when chart columns are missing", () => {
    const message: ChatMessage = {
      ...executedMessage,
      chart: {
        tipo: "bar",
        eixo_x: "missing",
        eixo_y: "total",
      },
    };
    renderWorkspace([userMessage, message]);

    fireEvent.click(screen.getByRole("button", { name: "Gerar Gráfico" }));

    expect(
      screen.getByText(
        "As colunas sugeridas pela IA para o gráfico não existem no resultado.",
      ),
    ).toBeInTheDocument();
  });
});
