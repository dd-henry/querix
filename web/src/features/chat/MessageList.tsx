import { Fragment, type ReactNode } from "react";

import type { ChatMessage } from "./useChat";

export interface MessageListProps {
  messages: ChatMessage[];
  onRetry: (requestId: string) => void;
  onCancelRequest?: () => void;
  pendingRequestId?: string;
  renderAfterMessage?: (message: ChatMessage) => ReactNode;
}

function liveStatus(messages: ChatMessage[]): string {
  const pending = messages.some((message) => message.status === "pending");
  if (pending) {
    return "Processando sua pergunta...";
  }
  const failed = messages.some((message) => message.status === "error");
  return failed ? "Uma solicitação precisa de atenção." : "";
}

export function MessageList({
  messages,
  onRetry,
  onCancelRequest,
  pendingRequestId,
  renderAfterMessage,
}: MessageListProps) {
  const pendingMessage = pendingRequestId
    ? messages.find(
        (message) =>
          message.role === "assistant" &&
          message.requestId === pendingRequestId,
      )
    : undefined;
  const progress = pendingMessage?.progress;
  return (
    <section className="message-list" aria-label="Mensagens da conversa">
      <div className="message-list__items">
        {messages.map((message) => {
          const isPending = message.status === "pending";
          const isError = message.status === "error";
          const isWarning = message.status === "warning";
          const retryDisabled =
            isPending || pendingRequestId === message.requestId;
          return (
            <Fragment key={`${message.requestId}:${message.role}`}>
              <article
                className={`chat-message chat-message--${message.role}${
                  isError
                    ? " chat-message--error"
                    : isWarning
                      ? " chat-message--warning"
                      : ""
                }`}
                data-message-id={`${message.requestId}:${message.role}`}
                data-message-status={message.status}
              >
                <p className="chat-message__author">
                  {message.role === "user" ? "Você" : "Ask SQL"}
                </p>
                {isPending ? (
                  <p className="chat-message__pending" role="presentation">
                    {message.content}
                  </p>
                ) : (
                  <p className="chat-message__content">{message.content}</p>
                )}
                {message.warnings.length > 0 ? (
                  <ul className="chat-message__warnings" aria-label="Avisos">
                    {message.warnings.map((warning) => (
                      <li key={warning}>{warning}</li>
                    ))}
                  </ul>
                ) : null}
                {isError && message.error ? (
                  <p className="chat-message__error-code">
                    Código: {message.error}
                  </p>
                ) : null}
                {message.retryable ? (
                  <button
                    type="button"
                    disabled={retryDisabled}
                    onClick={() => onRetry(message.requestId)}
                  >
                    Tentar novamente
                  </button>
                ) : null}
              </article>
              {renderAfterMessage?.(message)}
            </Fragment>
          );
        })}
      </div>
      <div className="message-list__live-status" role="status" aria-live="polite">
        {!pendingRequestId ? liveStatus(messages) : null}
        {pendingRequestId ? (
          <div
            className="chat-progress"
            aria-label="Progresso da consulta"
          >
            <span className="chat-progress__spinner" aria-hidden="true" />
            <span className="chat-progress__copy">
              <strong>
                {progress?.message ?? "A consulta está em andamento."}
              </strong>
              <span>
                {progress
                  ? `Tempo decorrido: ${progress.elapsed_seconds.toFixed(1)}s`
                  : "Aguardando atualização do servidor."}
              </span>
            </span>
          </div>
        ) : null}
        {pendingRequestId && onCancelRequest ? (
          <button
            className="chat-cancel-button"
            type="button"
            onClick={onCancelRequest}
            aria-label="Cancelar consulta em andamento"
          >
            <span className="chat-cancel-button__icon" aria-hidden="true">
              ×
            </span>
            <span>Cancelar consulta</span>
          </button>
        ) : null}
      </div>
    </section>
  );
}
