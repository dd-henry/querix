import { Fragment, type ReactNode } from "react";

import type { ChatMessage } from "./useChat";

export interface MessageListProps {
  messages: ChatMessage[];
  onRetry: (requestId: string) => void;
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
  pendingRequestId,
  renderAfterMessage,
}: MessageListProps) {
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
        {liveStatus(messages)}
      </div>
    </section>
  );
}
