import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  type ApiClient,
  type ChatResponse,
  type ConversationDetail,
} from "../../api/client";
import { useChat } from "./useChat";

const reviewResponse: ChatResponse = {
  conversation_id: "conversation-1",
  request_id: "request-1",
  status: "review",
  content: "SQL gerado para revisão.",
  sql: "SELECT 1",
  retryable: false,
  warnings: [],
};

function createClient(
  overrides: Partial<ApiClient["chat"]> = {},
): ApiClient {
  return {
    auth: {
      me: vi.fn(),
      login: vi.fn(),
      signup: vi.fn(),
      logout: vi.fn(),
    },
    conversations: {
      list: vi.fn(),
      get: vi.fn(),
      create: vi.fn(),
      favorite: vi.fn(),
      delete: vi.fn(),
    },
    chat: {
      translate: vi.fn().mockResolvedValue(reviewResponse),
      execute: vi.fn().mockResolvedValue({
        ...reviewResponse,
        status: "executed",
        content: "Aqui estão os resultados da consulta:",
        summary: "O faturamento retornado foi R$ 1,00.",
        result: {
          columns: ["total"],
          rows: [{ total: 1 }],
          row_count: 1,
          truncated: false,
        },
      }),
      status: vi.fn().mockResolvedValue({
        status: "running",
        phase: "generating_sql",
        message: "Interpretando sua pergunta e gerando a consulta.",
        elapsed_seconds: 1.2,
      }),
      cancel: vi.fn().mockResolvedValue({ status: "cancelled" }),
      retry: vi.fn().mockResolvedValue(reviewResponse),
      ...overrides,
    },
    history: {
      list: vi.fn(),
      pin: vi.fn(),
      delete: vi.fn(),
      rerun: vi.fn(),
    },
    predefined: {
      list: vi.fn(),
      favorite: vi.fn(),
      create: vi.fn(),
      update: vi.fn(),
      delete: vi.fn(),
      execute: vi.fn(),
    },
    admin: {
      listUsers: vi.fn(),
      updateStatus: vi.fn(),
      updateRole: vi.fn(),
    },
    schema: {
      sync: vi.fn(),
    },
  };
}

function Harness({
  client,
  reviewMode = true,
}: {
  client: ApiClient;
  reviewMode?: boolean;
}) {
  const chat = useChat({ client, reviewMode });
  const assistant = chat.messages.find(
    (message) => message.role === "assistant",
  );
  return (
    <>
      <output data-testid="messages">{JSON.stringify(chat.messages)}</output>
      <output data-testid="conversation">{chat.conversationId ?? ""}</output>
      <output data-testid="error">{chat.error ?? ""}</output>
      <button onClick={() => void chat.send("Show revenue")}>send</button>
      <button onClick={() => chat.cancelActiveRequest()}>cancel-request</button>
      <button
        onClick={() => {
          if (assistant) {
            void chat.confirmExecution(assistant.requestId);
          }
        }}
      >
        confirm
      </button>
      <button
        onClick={() => {
          if (assistant) {
            chat.cancelReview(assistant.requestId);
          }
        }}
      >
        cancel
      </button>
      <button
        onClick={() => {
          if (assistant) {
            void chat.retry(assistant.requestId);
          }
        }}
      >
        retry
      </button>
      <button onClick={() => void chat.openConversation("conversation-1")}>
        open
      </button>
    </>
  );
}

function readMessages(): Array<Record<string, unknown>> {
  return JSON.parse(screen.getByTestId("messages").textContent ?? "[]") as Array<
    Record<string, unknown>
  >;
}

function restoredConversation(): ConversationDetail {
  return {
    id: "conversation-1",
    title: "Revenue",
    is_favorite: false,
    created_at: "2025-01-15T10:00:00Z",
    last_activity: "2025-01-15T10:30:00Z",
    messages: [
      {
        id: 1,
        request_id: "request-1",
        role: "user",
        content: "Show revenue",
        sql: null,
        error: null,
        metadata: {},
        created_at: "2025-01-15T10:00:00Z",
      },
      {
        id: 2,
        request_id: "request-1",
        role: "assistant",
        content: "Consulta carregada.",
        sql: "SELECT 1",
        error: null,
        metadata: { retryable: false },
        created_at: "2025-01-15T10:00:01Z",
      },
    ],
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, resolve, reject };
}

beforeEach(() => {
  let id = 0;
  vi.stubGlobal("crypto", {
    randomUUID: () => `generated-${++id}`,
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useChat", () => {
  it("creates one user message and one pending assistant for a send", async () => {
    const request = deferred<ChatResponse>();
    const translate = vi.fn().mockReturnValue(request.promise);
    const client = createClient({ translate });
    render(<Harness client={client} />);

    fireEvent.click(screen.getByRole("button", { name: "send" }));

    expect(readMessages()).toEqual([
      expect.objectContaining({
        requestId: "generated-2",
        role: "user",
        content: "Show revenue",
      }),
      expect.objectContaining({
        requestId: "generated-2",
        role: "assistant",
        status: "pending",
      }),
    ]);
    expect(translate).toHaveBeenCalledWith({
      conversation_id: "generated-1",
      request_id: "generated-2",
      prompt: "Show revenue",
      review_mode: true,
    }, { signal: expect.any(AbortSignal) });

    request.resolve(reviewResponse);
    await waitFor(() =>
      expect(readMessages()[1]).toEqual(
        expect.objectContaining({
          status: "review",
          reviewState: "open",
          sql: "SELECT 1",
        }),
      ),
    );
  });

  it("updates the pending message with server progress", async () => {
    const request = deferred<ChatResponse>();
    const status = vi.fn().mockResolvedValue({
      status: "running",
      phase: "executing_query",
      message: "Executando a consulta no banco de dados.",
      elapsed_seconds: 4.2,
    });
    const client = createClient({
      translate: vi.fn().mockReturnValue(request.promise),
      status,
    });
    render(<Harness client={client} />);

    fireEvent.click(screen.getByRole("button", { name: "send" }));

    await waitFor(() =>
      expect(readMessages()[1]).toEqual(
        expect.objectContaining({
          progress: expect.objectContaining({
            phase: "executing_query",
            elapsed_seconds: 4.2,
          }),
        }),
      ),
    );
    expect(status).toHaveBeenCalledWith(
      {
        conversation_id: "generated-1",
        request_id: "generated-2",
      },
      { signal: expect.any(AbortSignal) },
    );

    request.resolve(reviewResponse);
    await waitFor(() =>
      expect(readMessages()[1]).toEqual(
        expect.objectContaining({ status: "review" }),
      ),
    );
  });

  it("stops a request after the status endpoint stays unavailable", async () => {
    vi.useFakeTimers();
    try {
      const request = deferred<ChatResponse>();
      const status = vi.fn().mockRejectedValue(
        new ApiError(
          "request_not_active",
          "The chat request is no longer active.",
          404,
        ),
      );
      const client = createClient({
        translate: vi.fn().mockReturnValue(request.promise),
        status,
      });
      render(<Harness client={client} />);

      fireEvent.click(screen.getByRole("button", { name: "send" }));
      await act(async () => {
        await Promise.resolve();
      });
      expect(status).toHaveBeenCalledOnce();

      await act(async () => {
        await vi.advanceTimersByTimeAsync(1_500);
      });

      expect(status).toHaveBeenCalledOnce();
      expect(readMessages()[1]).toEqual(
        expect.objectContaining({
          progress: expect.objectContaining({
            elapsed_seconds: expect.any(Number),
          }),
        }),
      );

      await act(async () => {
        await vi.advanceTimersByTimeAsync(28_000);
      });
      expect(readMessages()[1]).toEqual(
        expect.objectContaining({
          progress: expect.objectContaining({
            elapsed_seconds: expect.any(Number),
          }),
        }),
      );

      await act(async () => {
        await vi.advanceTimersByTimeAsync(2_000);
      });
      expect(readMessages()[1]).toEqual(
        expect.objectContaining({
          content: "A conexão com o servidor foi perdida durante a consulta.",
          status: "error",
          error: "request_lost",
          retryable: true,
        }),
      );

      request.resolve(reviewResponse);
    } finally {
      vi.useRealTimers();
    }
  });

  it("stores interpretation and diagnostics on the same assistant message", async () => {
    const translate = vi.fn().mockResolvedValue({
      ...reviewResponse,
      interpretation: {
        intent: "Comparar receita por região",
        dimensions: ["region"],
        metrics: ["revenue"],
        period: null,
        assumptions: ["revenue is the order total"],
      },
      diagnostics: {
        kind: "empty_result",
        message: "A consulta não encontrou dados compatíveis.",
        expected_columns: [],
      },
    });
    const client = createClient({ translate });
    render(<Harness client={client} />);

    fireEvent.click(screen.getByRole("button", { name: "send" }));

    await waitFor(() =>
      expect(readMessages()[1]).toEqual(
        expect.objectContaining({
          interpretation: expect.objectContaining({
            dimensions: ["region"],
          }),
          diagnostics: expect.objectContaining({
            kind: "empty_result",
          }),
        }),
      ),
    );
    expect(readMessages()).toHaveLength(2);
  });

  it("ignores a double-click while reusing the same request", () => {
    const request = deferred<ChatResponse>();
    const translate = vi.fn().mockReturnValue(request.promise);
    const client = createClient({ translate });
    render(<Harness client={client} />);

    fireEvent.click(screen.getByRole("button", { name: "send" }));
    fireEvent.click(screen.getByRole("button", { name: "send" }));

    expect(readMessages()).toHaveLength(2);
    expect(translate).toHaveBeenCalledOnce();
    expect(translate.mock.calls[0][0].request_id).toBe("generated-2");
  });

  it("cancels an active request and ignores a late response", async () => {
    const request = deferred<ChatResponse>();
    const translate = vi.fn().mockReturnValue(request.promise);
    const cancel = vi.fn().mockResolvedValue({ status: "cancelled" });
    const client = createClient({ translate, cancel });
    render(<Harness client={client} />);

    fireEvent.click(screen.getByRole("button", { name: "send" }));
    fireEvent.click(
      screen.getByRole("button", { name: "cancel-request" }),
    );

    expect(readMessages()[1]).toEqual(
      expect.objectContaining({
        status: "cancelled",
        content: "Consulta cancelada.",
      }),
    );
    expect(translate.mock.calls[0][1].signal.aborted).toBe(true);
    expect(cancel).toHaveBeenCalledWith({
      conversation_id: "generated-1",
      request_id: "generated-2",
    });

    request.resolve(reviewResponse);
    await waitFor(() =>
      expect(readMessages()[1]).toEqual(
        expect.objectContaining({
          status: "cancelled",
          content: "Consulta cancelada.",
        }),
      ),
    );
  });

  it("executes only after review confirmation and updates the target", async () => {
    const execute = vi.fn().mockResolvedValue({
      ...reviewResponse,
      status: "executed",
      content: "Aqui estão os resultados da consulta:",
    });
    const client = createClient({ execute });
    render(<Harness client={client} />);

    fireEvent.click(screen.getByRole("button", { name: "send" }));
    await waitFor(() =>
      expect(readMessages()[1]).toEqual(
        expect.objectContaining({ reviewState: "open" }),
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "confirm" }));

    await waitFor(() =>
      expect(readMessages()[1]).toEqual(
        expect.objectContaining({
          status: "executed",
          reviewState: "confirmed",
        }),
      ),
    );
    expect(execute).toHaveBeenCalledWith({
      conversation_id: "generated-1",
      request_id: "generated-2",
    }, { signal: expect.any(AbortSignal) });
    expect(readMessages()).toHaveLength(2);
  });

  it("restores stored SQL as re-executable and updates the same assistant", async () => {
    const execute = vi.fn().mockResolvedValue({
      ...reviewResponse,
      status: "executed",
      content: "Resultado atualizado.",
      result: {
        columns: ["total"],
        rows: [{ total: 4 }],
        row_count: 1,
        truncated: false,
      },
    });
    const client = createClient({ execute });
    vi.mocked(client.conversations.get).mockResolvedValue(
      restoredConversation(),
    );
    render(<Harness client={client} />);

    fireEvent.click(screen.getByRole("button", { name: "open" }));
    await waitFor(() =>
      expect(readMessages()[1]).toEqual(
        expect.objectContaining({
          sql: "SELECT 1",
          reexecuteAvailable: true,
        }),
      ),
    );

    fireEvent.click(screen.getByRole("button", { name: "confirm" }));
    await waitFor(() =>
      expect(readMessages()[1]).toEqual(
        expect.objectContaining({
          status: "executed",
          content: "Resultado atualizado.",
          result: expect.objectContaining({ row_count: 1 }),
        }),
      ),
    );
    expect(execute).toHaveBeenCalledWith({
      conversation_id: "conversation-1",
      request_id: "request-1",
    }, { signal: expect.any(AbortSignal) });
    expect(execute.mock.calls[0][0]).not.toHaveProperty("sql");
    expect(readMessages()).toHaveLength(2);
  });

  it("restores interpretation and diagnostics from conversation metadata", async () => {
    const detail = restoredConversation();
    detail.messages[1].metadata = {
      interpretation: {
        intent: "Comparar receita por região",
        dimensions: ["region"],
        metrics: ["revenue"],
        period: null,
        assumptions: ["revenue is the order total"],
      },
      diagnostics: {
        kind: "empty_result",
        message: "A consulta não encontrou dados compatíveis.",
        expected_columns: [],
      },
    };
    const client = createClient();
    vi.mocked(client.conversations.get).mockResolvedValue(detail);
    render(<Harness client={client} />);

    fireEvent.click(screen.getByRole("button", { name: "open" }));

    await waitFor(() =>
      expect(readMessages()[1]).toEqual(
        expect.objectContaining({
          interpretation: expect.objectContaining({ intent: "Comparar receita por região" }),
          diagnostics: expect.objectContaining({ kind: "empty_result" }),
        }),
      ),
    );
    expect(readMessages()).toHaveLength(2);
  });

  it("restores inferred join warnings from conversation metadata", async () => {
    const detail = restoredConversation();
    detail.messages[1].metadata = {
      warnings: ["JOIN inferido: orders.id -> customers.id."],
    };
    const client = createClient();
    vi.mocked(client.conversations.get).mockResolvedValue(detail);
    render(<Harness client={client} />);

    fireEvent.click(screen.getByRole("button", { name: "open" }));

    await waitFor(() =>
      expect(readMessages()[1]).toEqual(
        expect.objectContaining({
          warnings: ["JOIN inferido: orders.id -> customers.id."],
        }),
      ),
    );
  });

  it("keeps a restored query retryable after execution fails", async () => {
    const execute = vi.fn().mockRejectedValue(
      new ApiError("database_unavailable", "Banco indisponível.", 503),
    );
    const client = createClient({ execute });
    vi.mocked(client.conversations.get).mockResolvedValue(
      restoredConversation(),
    );
    render(<Harness client={client} />);

    fireEvent.click(screen.getByRole("button", { name: "open" }));
    await waitFor(() =>
      expect(readMessages()[1]).toEqual(
        expect.objectContaining({ reexecuteAvailable: true }),
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "confirm" }));

    await waitFor(() =>
      expect(readMessages()[1]).toEqual(
        expect.objectContaining({
          requestId: "request-1",
          status: "error",
          retryable: true,
          retryKind: "execute",
        }),
      ),
    );
    expect(readMessages()).toHaveLength(2);
  });

  it("does not execute a restored query twice while the first request is pending", async () => {
    const execution = deferred<ChatResponse>();
    const execute = vi.fn().mockReturnValue(execution.promise);
    const client = createClient({ execute });
    vi.mocked(client.conversations.get).mockResolvedValue(
      restoredConversation(),
    );
    render(<Harness client={client} />);

    fireEvent.click(screen.getByRole("button", { name: "open" }));
    await waitFor(() =>
      expect(readMessages()[1]).toEqual(
        expect.objectContaining({ reexecuteAvailable: true }),
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "confirm" }));
    fireEvent.click(screen.getByRole("button", { name: "confirm" }));

    expect(execute).toHaveBeenCalledOnce();
    execution.resolve({
      ...reviewResponse,
      status: "executed",
      content: "Resultado atualizado.",
    });
    await waitFor(() =>
      expect(readMessages()[1]).toEqual(
        expect.objectContaining({ status: "executed" }),
      ),
    );
  });

  it("cancels review without executing or adding another message", async () => {
    const client = createClient();
    render(<Harness client={client} />);

    fireEvent.click(screen.getByRole("button", { name: "send" }));
    await waitFor(() =>
      expect(readMessages()[1]).toEqual(
        expect.objectContaining({ reviewState: "open" }),
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "cancel" }));

    expect(readMessages()[1]).toEqual(
      expect.objectContaining({ reviewState: "cancelled" }),
    );
    expect(client.chat.execute).not.toHaveBeenCalled();
    expect(readMessages()).toHaveLength(2);
  });

  it("uses automatic execution when review mode is disabled", async () => {
    const translate = vi.fn().mockResolvedValue({
      ...reviewResponse,
      status: "executed",
      content: "Aqui estão os resultados da consulta:",
      summary: "O faturamento retornado foi R$ 1,00.",
      insights: [
        {
          key: "kpi",
          title: "Indicadores do período",
          summary: "A consulta retornou 1 linha(s).",
          result: {
            columns: ["total"],
            rows: [{ total: 1 }],
            row_count: 1,
            truncated: false,
          },
        },
      ],
    });
    const client = createClient({ translate });
    render(<Harness client={client} reviewMode={false} />);

    fireEvent.click(screen.getByRole("button", { name: "send" }));

    await waitFor(() =>
      expect(readMessages()[1]).toEqual(
        expect.objectContaining({ status: "executed" }),
      ),
    );
    expect(readMessages()[1].summary).toBe(
      "O faturamento retornado foi R$ 1,00.",
    );
    expect(readMessages()[1].insights).toEqual([
      expect.objectContaining({ key: "kpi" }),
    ]);
    expect(readMessages()).toHaveLength(2);
    expect(translate).toHaveBeenCalledWith(
      expect.objectContaining({ review_mode: false }),
      { signal: expect.any(AbortSignal) },
    );
    expect(client.chat.execute).not.toHaveBeenCalled();
  });

  it("stores translator warnings without offering an execution path", async () => {
    const translate = vi.fn().mockResolvedValue({
      ...reviewResponse,
      status: "warning",
      content: "AVISO: tabela não encontrada.",
      sql: null,
    });
    const client = createClient({ translate });
    render(<Harness client={client} reviewMode={false} />);

    fireEvent.click(screen.getByRole("button", { name: "send" }));

    await waitFor(() =>
      expect(readMessages()[1]).toEqual(
        expect.objectContaining({
          status: "warning",
          content: "AVISO: tabela não encontrada.",
        }),
      ),
    );
    expect(readMessages()[1].reviewState).toBeUndefined();
    expect(client.chat.execute).not.toHaveBeenCalled();
  });

  it("keeps the user message and retries a translation failure", async () => {
    const retry = vi.fn().mockResolvedValue(reviewResponse);
    const translate = vi.fn().mockRejectedValue(
      new ApiError(
        "translator_unavailable",
        "O tradutor está indisponível.",
        502,
      ),
    );
    const client = createClient({ translate, retry });
    render(<Harness client={client} />);

    fireEvent.click(screen.getByRole("button", { name: "send" }));
    await waitFor(() =>
      expect(readMessages()[1]).toEqual(
        expect.objectContaining({
          status: "error",
          error: "translator_unavailable",
          retryable: true,
          retryKind: "translate",
        }),
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "retry" }));

    await waitFor(() =>
      expect(readMessages()[1]).toEqual(
        expect.objectContaining({
          status: "review",
          reviewState: "open",
        }),
      ),
    );
    expect(retry).toHaveBeenCalledWith({
      conversation_id: "generated-1",
      request_id: "generated-2",
    }, { signal: expect.any(AbortSignal) });
    expect(readMessages()).toHaveLength(2);
  });

  it("retries database failures without creating a second user message", async () => {
    const retry = vi.fn().mockResolvedValue({
      ...reviewResponse,
      status: "executed",
      content: "Aqui estão os resultados da consulta:",
    });
    const execute = vi.fn().mockRejectedValue(
      new ApiError("database_unavailable", "Banco indisponível.", 503),
    );
    const client = createClient({ execute, retry });
    render(<Harness client={client} />);

    fireEvent.click(screen.getByRole("button", { name: "send" }));
    await waitFor(() =>
      expect(readMessages()[1]).toEqual(
        expect.objectContaining({ reviewState: "open" }),
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "confirm" }));
    await waitFor(() =>
      expect(readMessages()[1]).toEqual(
        expect.objectContaining({
          status: "error",
          retryKind: "execute",
        }),
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "retry" }));

    await waitFor(() =>
      expect(readMessages()[1]).toEqual(
        expect.objectContaining({ status: "executed" }),
      ),
    );
    expect(retry).toHaveBeenCalledWith({
      conversation_id: "generated-1",
      request_id: "generated-2",
    }, { signal: expect.any(AbortSignal) });
    expect(readMessages()).toHaveLength(2);
  });
});
