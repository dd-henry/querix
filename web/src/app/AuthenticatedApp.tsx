import { useEffect, useRef, useState } from "react";

import type { Profile } from "../api/client";
import { AppShell } from "./AppShell";
import { ChatWorkspace } from "../features/chat/ChatWorkspace";
import { useChat } from "../features/chat/useChat";
import { ConversationSidebar } from "../features/conversations/ConversationSidebar";
import { UserAdminPanel } from "../features/admin/UserAdminPanel";
import { HistoryPanel } from "../features/history/HistoryPanel";
import { PredefinedQueriesPanel } from "../features/predefined/PredefinedQueriesPanel";
import { SyncDatabaseButton } from "../features/settings/SyncDatabaseButton";
import type { AuthProviderProps } from "./AuthProvider";

type ActivePanel = "chat" | "history" | "predefined" | "admin" | "settings";

const panelCopy: Record<
  ActivePanel,
  { eyebrow: string; title: string; ariaLabel: string }
> = {
  chat: {
    eyebrow: "Conversa",
    title: "Converse com seus dados",
    ariaLabel: "Chat",
  },
  history: {
    eyebrow: "Consultas salvas",
    title: "Histórico",
    ariaLabel: "Histórico de consultas",
  },
  predefined: {
    eyebrow: "Catálogo",
    title: "Consultas compartilhadas",
    ariaLabel: "Consultas compartilhadas",
  },
  admin: {
    eyebrow: "Acesso",
    title: "Administração de usuários",
    ariaLabel: "Administração de usuários",
  },
  settings: {
    eyebrow: "Schema",
    title: "Configurações",
    ariaLabel: "Configurações",
  },
};

interface AuthenticatedAppProps {
  client: NonNullable<AuthProviderProps["client"]>;
  profile: Profile;
  onSignOut: () => void | Promise<void>;
}

export function AuthenticatedApp({
  client,
  profile,
  onSignOut,
}: AuthenticatedAppProps) {
  const [activePanel, setActivePanel] = useState<ActivePanel>("chat");
  const panelRef = useRef<HTMLDivElement>(null);
  const chat = useChat({ client, reviewMode: false });
  const copy = panelCopy[activePanel];

  useEffect(() => {
    if (activePanel !== "chat") {
      panelRef.current?.focus();
    }
  }, [activePanel]);

  const selectPanel = (panel: ActivePanel, closeSidebar?: () => void) => {
    setActivePanel(panel);
    closeSidebar?.();
  };

  const chatView = (
    <ChatWorkspace
      messages={chat.messages}
      error={chat.error}
      onSend={chat.send}
      onCancelRequest={chat.cancelActiveRequest}
      onRetry={chat.retry}
      onConfirmExecution={chat.confirmExecution}
      onCancelReview={chat.cancelReview}
    />
  );

  const content =
    activePanel === "chat" ? (
      chatView
    ) : activePanel === "history" ? (
      <HistoryPanel
        client={client}
        conversationId={chat.conversationId}
        onRerunResult={(response) => {
          chat.appendChatResponse(response);
          setActivePanel("chat");
        }}
      />
    ) : activePanel === "predefined" ? (
      <PredefinedQueriesPanel
        client={client}
        role={profile.role}
        onExecutionResult={(response) => {
          chat.appendPredefinedResult(response);
          setActivePanel("chat");
        }}
      />
    ) : activePanel === "admin" ? (
      <UserAdminPanel client={client} role={profile.role} />
    ) : (
      <SyncDatabaseButton client={client} />
    );

  return (
    <AppShell
      profile={profile}
      onSignOut={onSignOut}
      mainEyebrow={copy.eyebrow}
      mainTitle={copy.title}
      mainAriaLabel={copy.ariaLabel}
      sidebar={(closeSidebar) => (
        <>
          <ConversationSidebar
            client={client}
            selectedConversationId={chat.conversationId}
            onSelect={(conversationId) => {
              chat.openConversation(conversationId);
              selectPanel("chat", closeSidebar);
            }}
            onNewConversation={() => {
              chat.newConversation();
              selectPanel("chat", closeSidebar);
            }}
            onCloseMobile={closeSidebar}
          />
          <nav aria-label="Seções">
            <ul>
              <li>
                <button
                  type="button"
                  aria-current={activePanel === "chat" ? "page" : undefined}
                  onClick={() => selectPanel("chat", closeSidebar)}
                >
                  Conversa
                </button>
              </li>
              <li>
                <button
                  type="button"
                  aria-current={activePanel === "history" ? "page" : undefined}
                  onClick={() => selectPanel("history", closeSidebar)}
                >
                  Histórico
                </button>
              </li>
              <li>
                <button
                  type="button"
                  aria-current={
                    activePanel === "predefined" ? "page" : undefined
                  }
                  onClick={() => selectPanel("predefined", closeSidebar)}
                >
                  Consultas compartilhadas
                </button>
              </li>
              {profile.role === "admin" ? (
                <li>
                  <button
                    type="button"
                    aria-current={activePanel === "admin" ? "page" : undefined}
                    onClick={() => selectPanel("admin", closeSidebar)}
                  >
                    Administração
                  </button>
                </li>
              ) : null}
              <li>
                <button
                  type="button"
                  aria-current={
                    activePanel === "settings" ? "page" : undefined
                  }
                  onClick={() => selectPanel("settings", closeSidebar)}
                >
                  Configurações
                </button>
              </li>
            </ul>
          </nav>
        </>
      )}
      chat={
        <div
          ref={panelRef}
          className="authenticated-panel"
          tabIndex={activePanel === "chat" ? undefined : -1}
          aria-label={copy.ariaLabel}
        >
          {content}
        </div>
      }
    />
  );
}
