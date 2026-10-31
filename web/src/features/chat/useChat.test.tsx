import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  type ApiClient,
  type ChatResponse,
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
        result: {
          columns: ["total"],
          rows: [{ total: 1 }],
          row_count: 1,
          truncated: false,
        },
      }),
      retry: vi.fn().mockResolvedValue(reviewResponse),
      ...overrides,
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
    </>
  );
}

function readMessages(): Array<Record<string, unknown>> {
  return JSON.parse(screen.getByTestId("messages").textContent ?? "[]") as Array<
    Record<string, unknown>
  >;
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
    });

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
    });
    expect(readMessages()).toHaveLength(2);
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
    });
    const client = createClient({ translate });
    render(<Harness client={client} reviewMode={false} />);

    fireEvent.click(screen.getByRole("button", { name: "send" }));

    await waitFor(() =>
      expect(readMessages()[1]).toEqual(
        expect.objectContaining({ status: "executed" }),
      ),
    );
    expect(translate).toHaveBeenCalledWith(
      expect.objectContaining({ review_mode: false }),
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
    });
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
    });
    expect(readMessages()).toHaveLength(2);
  });
});
