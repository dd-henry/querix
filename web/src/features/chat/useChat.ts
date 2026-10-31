import { useCallback, useRef, useState } from "react";

import {
  ApiError,
  type ApiClient,
  type ChatResponse,
  type ChatRetryKind,
  type ChatStatus,
  type ChatResultPayload,
} from "../../api/client";

export type ChatMessageStatus = ChatStatus | "pending" | "error";
export type ChatReviewState = "open" | "cancelled" | "confirmed";

export interface ChatMessage {
  requestId: string;
  role: "user" | "assistant";
  content: string;
  status?: ChatMessageStatus;
  sql?: string;
  error?: string;
  retryable?: boolean;
  retryKind?: ChatRetryKind;
  chart?: Record<string, unknown>;
  result?: ChatResultPayload;
  warnings: string[];
  reviewState?: ChatReviewState;
}

export interface UseChatOptions {
  client: ApiClient;
  conversationId?: string;
  reviewMode?: boolean;
}

export interface UseChatResult {
  conversationId?: string;
  messages: ChatMessage[];
  error: string | null;
  send: (prompt: string) => Promise<boolean>;
  confirmExecution: (requestId: string) => Promise<boolean>;
  cancelReview: (requestId: string) => void;
  retry: (requestId: string) => Promise<boolean>;
  openConversation: (conversationId: string) => void;
}

interface ActiveRequest {
  requestId: string;
  promise: Promise<boolean>;
}

function createId(): string {
  if (typeof crypto === "undefined" || !crypto.randomUUID) {
    throw new Error("The browser does not support stable request IDs.");
  }
  return crypto.randomUUID();
}

function describeError(error: unknown): { code: string; message: string } {
  if (error instanceof ApiError) {
    return { code: error.code, message: error.message };
  }
  if (error instanceof Error && error.message) {
    return { code: "request_failed", message: error.message };
  }
  return {
    code: "request_failed",
    message: "Não foi possível concluir a solicitação.",
  };
}

function responseMessage(
  current: ChatMessage,
  response: ChatResponse,
): ChatMessage {
  return {
    ...current,
    content: response.content,
    status: response.status,
    sql: response.sql ?? undefined,
    chart: response.chart ?? undefined,
    result: response.result ?? undefined,
    retryable: response.retryable,
    retryKind: response.retry_kind ?? undefined,
    error: undefined,
    warnings: response.warnings ?? [],
    reviewState:
      response.status === "review"
        ? "open"
        : response.status === "executed"
          ? "confirmed"
          : undefined,
  };
}

function replaceAssistant(
  messages: ChatMessage[],
  requestId: string,
  update: (message: ChatMessage) => ChatMessage,
): ChatMessage[] {
  return messages.map((message) =>
    message.role === "assistant" && message.requestId === requestId
      ? update(message)
      : message,
  );
}

export function useChat({
  client,
  conversationId: initialConversationId,
  reviewMode = true,
}: UseChatOptions): UseChatResult {
  const [conversationId, setConversationId] = useState(
    initialConversationId,
  );
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [error, setError] = useState<string | null>(null);
  const conversationIdRef = useRef(initialConversationId);
  const activeRequestRef = useRef<ActiveRequest | null>(null);

  const updateAssistant = useCallback(
    (
      requestId: string,
      update: (message: ChatMessage) => ChatMessage,
    ) => {
      setMessages((current) => replaceAssistant(current, requestId, update));
    },
    [],
  );

  const startRequest = useCallback(
    (
      requestId: string,
      operation: () => Promise<ChatResponse>,
      retryKind: ChatRetryKind,
    ): Promise<boolean> => {
      const activeRequest = activeRequestRef.current;
      if (activeRequest) {
        return activeRequest.promise;
      }

      const promise = (async () => {
        try {
          const response = await operation();
          updateAssistant(requestId, (current) =>
            responseMessage(current, response),
          );
          return true;
        } catch (requestError: unknown) {
          const described = describeError(requestError);
          updateAssistant(requestId, (current) => ({
            ...current,
            content: described.message,
            status: "error",
            error: described.code,
            retryable: true,
            retryKind,
          }));
          return false;
        } finally {
          if (activeRequestRef.current?.requestId === requestId) {
            activeRequestRef.current = null;
          }
        }
      })();
      activeRequestRef.current = { requestId, promise };
      return promise;
    },
    [updateAssistant],
  );

  const send = useCallback(
    (prompt: string) => {
      const normalizedPrompt = prompt.trim();
      if (!normalizedPrompt || normalizedPrompt.length > 2_000) {
        const message =
          "A pergunta deve conter entre 1 e 2.000 caracteres.";
        setError(message);
        return Promise.resolve(false);
      }

      const activeRequest = activeRequestRef.current;
      if (activeRequest) {
        return activeRequest.promise;
      }

      setError(null);
      const nextConversationId =
        conversationIdRef.current ?? createId();
      const requestId = createId();
      conversationIdRef.current = nextConversationId;
      setConversationId(nextConversationId);
      setMessages((current) => [
        ...current,
        {
          requestId,
          role: "user",
          content: normalizedPrompt,
          warnings: [],
        },
        {
          requestId,
          role: "assistant",
          content: "Processando sua pergunta...",
          status: "pending",
          retryable: false,
          warnings: [],
        },
      ]);

      return startRequest(
        requestId,
        () =>
          client.chat.translate({
            conversation_id: nextConversationId,
            request_id: requestId,
            prompt: normalizedPrompt,
            review_mode: reviewMode,
          }),
        "translate",
      );
    },
    [client, reviewMode, startRequest],
  );

  const confirmExecution = useCallback(
    (requestId: string) => {
      const activeRequest = activeRequestRef.current;
      if (activeRequest) {
        return activeRequest.promise;
      }
      const current = messages.find(
        (message) =>
          message.role === "assistant" && message.requestId === requestId,
      );
      if (!current || !conversationIdRef.current) {
        const message = "A consulta revisada não está disponível.";
        setError(message);
        return Promise.resolve(false);
      }
      const activeConversationId = conversationIdRef.current;

      setError(null);
      updateAssistant(requestId, (message) => ({
        ...message,
        content: "Executando a consulta...",
        status: "pending",
        error: undefined,
        reviewState: "confirmed",
      }));
      return startRequest(
        requestId,
        () =>
          client.chat.execute({
            conversation_id: activeConversationId,
            request_id: requestId,
          }),
        "execute",
      );
    },
    [client, messages, startRequest, updateAssistant],
  );

  const cancelReview = useCallback(
    (requestId: string) => {
      updateAssistant(requestId, (message) => ({
        ...message,
        reviewState: "cancelled",
      }));
    },
    [updateAssistant],
  );

  const retry = useCallback(
    (requestId: string) => {
      const activeRequest = activeRequestRef.current;
      if (activeRequest) {
        return activeRequest.promise;
      }
      if (!conversationIdRef.current) {
        const message = "A conversa desta solicitação não está disponível.";
        setError(message);
        return Promise.resolve(false);
      }
      const activeConversationId = conversationIdRef.current;

      const current = messages.find(
        (message) =>
          message.role === "assistant" && message.requestId === requestId,
      );
      if (!current?.retryable) {
        const message = "Esta solicitação não pode ser repetida.";
        setError(message);
        return Promise.resolve(false);
      }

      setError(null);
      updateAssistant(requestId, (message) => ({
        ...message,
        content: "Tentando novamente...",
        status: "pending",
        error: undefined,
      }));
      return startRequest(
        requestId,
        () =>
          client.chat.retry({
            conversation_id: activeConversationId,
            request_id: requestId,
          }),
        current.retryKind ?? "translate",
      );
    },
    [client, messages, startRequest, updateAssistant],
  );

  const openConversation = useCallback((nextConversationId: string) => {
    const normalizedId = nextConversationId.trim();
    if (!normalizedId) {
      setError("O identificador da conversa é obrigatório.");
      return;
    }
    if (activeRequestRef.current) {
      setError("Aguarde a solicitação atual terminar.");
      return;
    }
    conversationIdRef.current = normalizedId;
    setConversationId(normalizedId);
    setMessages([]);
    setError(null);
  }, []);

  return {
    conversationId,
    messages,
    error,
    send,
    confirmExecution,
    cancelReview,
    retry,
    openConversation,
  };
}
