import { useCallback, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  type ApiClient,
  type ConversationGroup,
  type ConversationSummary,
} from "../../api/client";

export interface ConversationSidebarProps {
  client: ApiClient;
  selectedConversationId?: string;
  onSelect?: (conversationId: string) => void;
  onNewConversation?: () => void;
  onCloseMobile?: () => void;
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "Não foi possível carregar as conversas.";
}

function updateConversation(
  groups: ConversationGroup[],
  conversationId: string,
  update: (conversation: ConversationSummary) => ConversationSummary,
): ConversationGroup[] {
  return groups.map((group) => ({
    ...group,
    conversations: group.conversations.map((conversation) =>
      conversation.id === conversationId
        ? update(conversation)
        : conversation,
    ),
  }));
}

function removeConversation(
  groups: ConversationGroup[],
  conversationId: string,
): ConversationGroup[] {
  return groups.map((group) => ({
    ...group,
    conversations: group.conversations.filter(
      (conversation) => conversation.id !== conversationId,
    ),
  }));
}

export function ConversationSidebar({
  client,
  selectedConversationId,
  onSelect,
  onNewConversation,
  onCloseMobile,
}: ConversationSidebarProps) {
  const [groups, setGroups] = useState<ConversationGroup[]>([]);
  const [expiredCount, setExpiredCount] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(
    selectedConversationId ?? null,
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const timezone = useMemo(
    () => Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
    [],
  );

  const loadConversations = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await client.conversations.list(timezone);
      setGroups(response.groups);
      setExpiredCount(response.expired_count);
    } catch (loadError: unknown) {
      setError(errorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, [client, timezone]);

  useEffect(() => {
    void loadConversations();
  }, [loadConversations]);

  useEffect(() => {
    setSelectedId(selectedConversationId ?? null);
  }, [selectedConversationId]);

  const conversations = groups.flatMap((group) => group.conversations);

  const handleNewConversation = () => {
    setSelectedId(null);
    setPendingDeleteId(null);
    onNewConversation?.();
    onCloseMobile?.();
  };

  const handleSelect = (conversationId: string) => {
    setSelectedId(conversationId);
    onSelect?.(conversationId);
    onCloseMobile?.();
  };

  const handleFavorite = async (conversation: ConversationSummary) => {
    setPendingAction(`favorite:${conversation.id}`);
    setError("");
    try {
      await client.conversations.favorite(
        conversation.id,
        !conversation.is_favorite,
      );
      setGroups((current) =>
        updateConversation(current, conversation.id, (item) => ({
          ...item,
          is_favorite: !item.is_favorite,
        })),
      );
    } catch (favoriteError: unknown) {
      setError(errorMessage(favoriteError));
    } finally {
      setPendingAction(null);
    }
  };

  const handleDelete = async (conversationId: string) => {
    setPendingAction(`delete:${conversationId}`);
    setError("");
    try {
      await client.conversations.delete(conversationId);
      setGroups((current) => removeConversation(current, conversationId));
      setPendingDeleteId(null);
      if (selectedId === conversationId) {
        setSelectedId(null);
      }
    } catch (deleteError: unknown) {
      setError(errorMessage(deleteError));
    } finally {
      setPendingAction(null);
    }
  };

  return (
    <section
      className="conversation-sidebar"
      aria-labelledby="conversation-sidebar-title"
    >
      <div className="conversation-sidebar__header">
        <div>
          <p className="eyebrow">Workspace</p>
          <h2 id="conversation-sidebar-title">Conversas</h2>
        </div>
        <button
          className="conversation-sidebar__new"
          type="button"
          onClick={handleNewConversation}
        >
          Nova conversa
        </button>
      </div>

      {loading ? (
        <p role="status">Carregando conversas...</p>
      ) : error ? (
        <div className="conversation-sidebar__feedback" role="alert">
          <p>{error}</p>
          <button type="button" onClick={() => void loadConversations()}>
            Tentar novamente
          </button>
        </div>
      ) : conversations.length === 0 ? (
        <p role="status">Nenhuma conversa ainda.</p>
      ) : (
        <>
          {expiredCount > 0 ? (
            <p className="conversation-sidebar__notice">
              {expiredCount} conversa(s) antiga(s) aguardam limpeza.
            </p>
          ) : null}
          <div className="conversation-sidebar__groups">
            {groups.map((group) =>
              group.conversations.length > 0 ? (
                <section key={group.key} aria-labelledby={`group-${group.key}`}>
                  <h3 id={`group-${group.key}`}>{group.label}</h3>
                  <ul>
                    {group.conversations.map((conversation) => {
                      const isSelected = selectedId === conversation.id;
                      const isFavoritePending =
                        pendingAction === `favorite:${conversation.id}`;
                      const isDeletePending =
                        pendingAction === `delete:${conversation.id}`;
                      return (
                        <li key={conversation.id}>
                          <div
                            className={`conversation-item${
                              isSelected ? " is-selected" : ""
                            }`}
                          >
                            <button
                              className="conversation-item__select"
                              type="button"
                              aria-label={`Abrir conversa ${conversation.title}`}
                              aria-current={
                                isSelected ? "page" : undefined
                              }
                              onClick={() => handleSelect(conversation.id)}
                            >
                              {conversation.title}
                            </button>
                            <div className="conversation-item__actions">
                              <button
                                type="button"
                                aria-label={
                                  conversation.is_favorite
                                    ? `Desfavoritar ${conversation.title}`
                                    : `Favoritar ${conversation.title}`
                                }
                                disabled={isFavoritePending || isDeletePending}
                                onClick={() => void handleFavorite(conversation)}
                              >
                                {conversation.is_favorite ? "★" : "☆"}
                              </button>
                              <button
                                type="button"
                                aria-label={`Excluir ${conversation.title}`}
                                disabled={isFavoritePending || isDeletePending}
                                onClick={() =>
                                  setPendingDeleteId(conversation.id)
                                }
                              >
                                Excluir
                              </button>
                            </div>
                          </div>
                          {pendingDeleteId === conversation.id ? (
                            <div
                              className="conversation-item__confirmation"
                              role="group"
                              aria-label={`Confirmar exclusão de ${conversation.title}`}
                            >
                              <span>Excluir esta conversa?</span>
                              <button
                                type="button"
                                disabled={isDeletePending}
                                onClick={() =>
                                  void handleDelete(conversation.id)
                                }
                              >
                                Confirmar exclusão
                              </button>
                              <button
                                type="button"
                                onClick={() => setPendingDeleteId(null)}
                              >
                                Cancelar
                              </button>
                            </div>
                          ) : null}
                        </li>
                      );
                    })}
                  </ul>
                </section>
              ) : null,
            )}
          </div>
        </>
      )}
    </section>
  );
}
