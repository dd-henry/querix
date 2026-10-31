import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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

  it("renders bounded results, truncation notice, and UTF-8 CSV download", () => {
    renderWorkspace([userMessage, executedMessage]);

    expect(screen.getByRole("table")).toBeInTheDocument();
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
