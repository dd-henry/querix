import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ChatMessage } from "./useChat";
import { MessageList } from "./MessageList";

const userMessage: ChatMessage = {
  requestId: "request-1",
  role: "user",
  content: "Show revenue",
  warnings: [],
};

const assistantMessage: ChatMessage = {
  requestId: "request-1",
  role: "assistant",
  content: "SQL gerado para revisão.",
  status: "review",
  sql: "SELECT 1",
  warnings: [],
};

describe("MessageList", () => {
  it("renders one stable bubble for each message and keeps earlier messages mounted", () => {
    const { rerender } = render(
      <MessageList
        messages={[userMessage, assistantMessage]}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getAllByRole("article")).toHaveLength(2);
    expect(screen.getAllByText("Show revenue")).toHaveLength(1);

    const pendingMessage: ChatMessage = {
      requestId: "request-2",
      role: "assistant",
      content: "Processando sua pergunta...",
      status: "pending",
      warnings: [],
    };
    rerender(
      <MessageList
        messages={[userMessage, assistantMessage, pendingMessage]}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getAllByRole("article")).toHaveLength(3);
    expect(screen.getAllByText("Show revenue")).toHaveLength(1);
  });

  it("shows a single live pending status", () => {
    render(
      <MessageList
        messages={[
          userMessage,
          {
            ...assistantMessage,
            status: "pending",
            content: "Processando sua pergunta...",
          },
        ]}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getAllByRole("status")).toHaveLength(1);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Processando sua pergunta...",
    );
  });

  it("shows cancellation without duplicating pending status text", () => {
    const onCancelRequest = vi.fn();
    render(
      <MessageList
        messages={[
          userMessage,
          {
            ...assistantMessage,
            status: "pending",
            content: "Processando sua pergunta...",
          },
        ]}
        onRetry={vi.fn()}
        pendingRequestId="request-1"
        onCancelRequest={onCancelRequest}
      />,
    );

    expect(screen.getByRole("button", { name: "Cancelar consulta em andamento" }))
      .toBeInTheDocument();
    expect(screen.getByRole("status")).not.toHaveTextContent(
      "Processando sua pergunta...",
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Cancelar consulta em andamento" }),
    );
    expect(onCancelRequest).toHaveBeenCalledOnce();
  });

  it("places attachments immediately after their assistant message", () => {
    const { container } = render(
      <MessageList
        messages={[
          userMessage,
          assistantMessage,
          {
            requestId: "request-2",
            role: "user",
            content: "Show profit",
            warnings: [],
          },
          {
            requestId: "request-2",
            role: "assistant",
            content: "Resultado calculado.",
            status: "executed",
            result: {
              columns: ["total"],
              rows: [{ total: 42 }],
              row_count: 1,
              truncated: false,
            },
            warnings: [],
          },
        ]}
        onRetry={vi.fn()}
        renderAfterMessage={(message) =>
          message.role === "assistant" && message.result ? (
            <div data-testid={`result-${message.requestId}`}>
              Resultado da consulta
            </div>
          ) : null
        }
      />,
    );

    const items = Array.from(
      container.querySelector(".message-list__items")?.children ?? [],
    ).map((item) => item.textContent);

    expect(items).toEqual([
      "VocêShow revenue",
      "Ask SQLSQL gerado para revisão.",
      "VocêShow profit",
      "Ask SQLResultado calculado.",
      "Resultado da consulta",
    ]);
  });

  it("renders warnings without a retry action", () => {
    render(
      <MessageList
        messages={[
          userMessage,
          {
            ...assistantMessage,
            status: "warning",
            content: "AVISO: tabela não encontrada.",
          },
        ]}
        onRetry={vi.fn()}
      />,
    );

    expect(
      screen.getByText("AVISO: tabela não encontrada."),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Tentar novamente" }),
    ).not.toBeInTheDocument();
  });

  it("renders retryable errors and disables only the pending request", () => {
    const onRetry = vi.fn();
    render(
      <MessageList
        messages={[
          userMessage,
          {
            ...assistantMessage,
            status: "error",
            content: "Banco indisponível.",
            error: "database_unavailable",
            retryable: true,
          },
        ]}
        onRetry={onRetry}
        pendingRequestId="request-1"
      />,
    );

    const retry = screen.getByRole("button", { name: "Tentar novamente" });
    expect(retry).toBeDisabled();
    expect(screen.getByText("Código: database_unavailable")).toBeInTheDocument();
  });

  it("invokes retry for the target request and announces failures", () => {
    const onRetry = vi.fn();
    render(
      <MessageList
        messages={[
          userMessage,
          {
            ...assistantMessage,
            status: "error",
            content: "O tradutor está indisponível.",
            error: "translator_unavailable",
            retryable: true,
          },
        ]}
        onRetry={onRetry}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Tentar novamente" }));

    expect(onRetry).toHaveBeenCalledWith("request-1");
    expect(screen.getByRole("status")).toHaveTextContent(
      "Uma solicitação precisa de atenção.",
    );
  });
});
