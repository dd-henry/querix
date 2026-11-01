export type UserRole = "user" | "dev" | "dba" | "admin";
export type ProfileStatus = "pending" | "approved" | "rejected" | "disabled";

export interface Profile {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  status: ProfileStatus;
}

export type AdminRole = "user" | "dev" | "admin";
export type AdminStatus = "approved" | "rejected" | "disabled";

export interface AdminProfile extends Omit<Profile, "role"> {
  role: AdminRole;
  created_at: string;
  approved_at?: string | null;
  disabled_at?: string | null;
}

export interface AdminProfileListResponse {
  profiles: AdminProfile[];
}

export interface SchemaSyncResponse {
  status: "synchronized";
}

export interface LoginInput {
  email: string;
  password: string;
}

export interface SignupInput extends LoginInput {
  name: string;
  password_confirmation: string;
}

export interface SignupResponse {
  message: string;
}

export type ConversationGroupKey =
  | "today"
  | "yesterday"
  | "last_7_days"
  | "last_30_days"
  | "older";

export interface ConversationSummary {
  id: string;
  title: string;
  is_favorite: boolean;
  created_at: string;
  last_activity: string;
}

export interface ConversationGroup {
  key: ConversationGroupKey;
  label: string;
  conversations: ConversationSummary[];
}

export interface ConversationListResponse {
  groups: ConversationGroup[];
  expired_count: number;
}

export interface ConversationDetail extends ConversationSummary {
  messages: ConversationMessage[];
}

export interface ConversationMessage {
  id: number;
  request_id: string;
  role: "user" | "assistant";
  content: string;
  sql?: string | null;
  error?: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface ConversationCreateInput {
  conversation_id: string;
  request_id: string;
  prompt: string;
}

export interface MessageResponse {
  message: string;
}

export type HistorySource = "chat" | "predefined";

export interface HistoryRecord {
  id: number;
  prompt: string;
  sql: string;
  parameters: Record<string, unknown>;
  source: HistorySource;
  session_id?: string | null;
  is_pinned: boolean;
  created_at: string;
}

export interface HistoryListResponse {
  records: HistoryRecord[];
}

export interface PredefinedParameter {
  name: string;
  label?: string | null;
  required: boolean;
}

export interface PredefinedQuery {
  id: number;
  name: string;
  description: string;
  sql: string;
  tags: string[];
  author: string;
  parameters: PredefinedParameter[];
  updated_at: string;
  is_favorite: boolean;
}

export interface PredefinedListResponse {
  queries: PredefinedQuery[];
}

export interface PredefinedWriteInput {
  name: string;
  description: string;
  sql: string;
  tags: string[];
  parameters: Array<Record<string, unknown>>;
}

export interface PredefinedExecutionResponse {
  query_id: number;
  result: ChatResultPayload;
}

export type ChatStatus = "review" | "translated" | "warning" | "executed";
export type ChatRetryKind = "translate" | "execute";

export interface ChatTranslateInput {
  conversation_id: string;
  request_id: string;
  prompt: string;
  review_mode: boolean;
}

export interface ChatRequestInput {
  conversation_id: string;
  request_id: string;
}

export interface ChatRequestOptions {
  signal?: AbortSignal;
}

export interface ChatResultPayload {
  columns: string[];
  rows: Array<Record<string, unknown>>;
  row_count: number;
  truncated: boolean;
}

export interface ChatInterpretation {
  intent: string;
  dimensions: string[];
  metrics: string[];
  period?: Record<string, unknown> | null;
  assumptions: string[];
}

export interface ChatDiagnostics {
  kind: string;
  message: string;
  expected_columns: string[];
}

export interface ChatInsight {
  key: string;
  title: string;
  summary?: string | null;
  sql?: string | null;
  result?: ChatResultPayload | null;
  warning?: string | null;
}

export interface ChatResponse {
  conversation_id: string;
  request_id: string;
  status: ChatStatus;
  content: string;
  sql?: string | null;
  chart?: Record<string, unknown> | null;
  summary?: string | null;
  result?: ChatResultPayload | null;
  insights?: ChatInsight[];
  interpretation?: ChatInterpretation | null;
  diagnostics?: ChatDiagnostics | null;
  retryable: boolean;
  retry_kind?: ChatRetryKind | null;
  warnings: string[];
}

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(code: string, message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

interface ApiErrorPayload {
  error?: {
    code?: unknown;
    message?: unknown;
  };
}

interface ApiClientOptions {
  fetchImpl?: typeof fetch;
  onUnauthorized?: () => void;
}

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
};

async function parseResponseBody(
  response: Response,
): Promise<unknown | undefined> {
  const text = await response.text();
  if (!text.trim()) {
    return undefined;
  }

  try {
    return JSON.parse(text) as unknown;
  } catch {
    throw new ApiError(
      "invalid_response",
      "The API returned an invalid response.",
      response.status,
    );
  }
}

function parseApiError(
  body: unknown,
  status: number,
): ApiError {
  const payload = body as ApiErrorPayload | undefined;
  const code = payload?.error?.code;
  const message = payload?.error?.message;
  if (typeof code === "string" && typeof message === "string") {
    return new ApiError(code, message, status);
  }
  return new ApiError(
    "invalid_error_response",
    "The API returned an invalid error response.",
    status,
  );
}

function requireResponse<T>(
  value: T | undefined,
  resource: string,
): T {
  if (value === undefined) {
    throw new ApiError(
      "invalid_response",
      `The API returned an empty ${resource} response.`,
      502,
    );
  }
  return value;
}

export function createApiClient({
  fetchImpl = fetch,
  onUnauthorized,
}: ApiClientOptions = {}) {
  async function request<T>(
    path: string,
    { body, headers, ...init }: RequestOptions = {},
  ): Promise<T | undefined> {
    const requestHeaders = new Headers(headers);
    if (body !== undefined) {
      requestHeaders.set("Content-Type", "application/json");
    }

    const response = await fetchImpl(path, {
      ...init,
      headers: requestHeaders,
      credentials: "include",
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const parsedBody = await parseResponseBody(response);

    if (!response.ok) {
      if (response.status === 401) {
        onUnauthorized?.();
      }
      throw parseApiError(parsedBody, response.status);
    }

    return parsedBody as T | undefined;
  }

  return {
    auth: {
      login: (input: LoginInput) =>
        request<Profile>("/api/auth/login", {
          method: "POST",
          body: input,
        }),
      signup: (input: SignupInput) =>
        request<SignupResponse>("/api/auth/signup", {
          method: "POST",
          body: input,
        }),
      logout: () =>
        request<MessageResponse>("/api/auth/logout", {
          method: "POST",
        }),
      me: () => request<Profile>("/api/auth/me"),
    },
    conversations: {
      list: async (timezone = "UTC") =>
        requireResponse(
          await request<ConversationListResponse>(
            `/api/conversations?timezone=${encodeURIComponent(timezone)}`,
          ),
          "conversation list",
        ),
      get: async (conversationId: string) =>
        requireResponse(
          await request<ConversationDetail>(
            `/api/conversations/${encodeURIComponent(conversationId)}`,
          ),
          "conversation detail",
        ),
      create: async (input: ConversationCreateInput) =>
        requireResponse(
          await request<{
            conversation_id: string;
            request_id: string;
          }>("/api/conversations", {
            method: "POST",
            body: input,
          }),
          "conversation creation",
        ),
      favorite: async (conversationId: string, isFavorite: boolean) =>
        requireResponse(
          await request<ConversationSummary>(
            `/api/conversations/${encodeURIComponent(conversationId)}`,
            {
              method: "PATCH",
              body: { is_favorite: isFavorite },
            },
          ),
          "conversation update",
        ),
      delete: async (conversationId: string) =>
        request<void>(
          `/api/conversations/${encodeURIComponent(conversationId)}?confirm=true`,
          {
            method: "DELETE",
          },
        ),
    },
    chat: {
      translate: async (
        input: ChatTranslateInput,
        options: ChatRequestOptions = {},
      ) =>
        requireResponse(
          await request<ChatResponse>("/api/chat/translate", {
            method: "POST",
            body: input,
            signal: options.signal,
          }),
          "chat translation",
        ),
      execute: async (
        input: ChatRequestInput,
        options: ChatRequestOptions = {},
      ) =>
        requireResponse(
          await request<ChatResponse>("/api/chat/execute", {
            method: "POST",
            body: input,
            signal: options.signal,
          }),
          "chat execution",
        ),
      retry: async (
        input: ChatRequestInput,
        options: ChatRequestOptions = {},
      ) =>
        requireResponse(
          await request<ChatResponse>("/api/chat/retry", {
            method: "POST",
            body: input,
            signal: options.signal,
          }),
          "chat retry",
        ),
    },
    history: {
      list: async () =>
        requireResponse(
          await request<HistoryListResponse>("/api/history"),
          "history list",
        ),
      pin: async (historyId: number, isPinned: boolean) =>
        requireResponse(
          await request<{ id: number; is_pinned: boolean }>(
            `/api/history/${historyId}`,
            {
              method: "PATCH",
              body: { is_pinned: isPinned },
            },
          ),
          "history update",
        ),
      delete: async (historyId: number) =>
        requireResponse(
          await request<{ id: number; is_pinned: boolean }>(
            `/api/history/${historyId}`,
            {
              method: "DELETE",
            },
          ),
          "history deletion",
        ),
      rerun: async (historyId: number, input: ChatRequestInput) =>
        requireResponse(
          await request<ChatResponse>(
            `/api/history/${historyId}/rerun`,
            {
              method: "POST",
              body: input,
            },
          ),
          "history rerun",
        ),
    },
    predefined: {
      list: async (search = "") =>
        requireResponse(
          await request<PredefinedListResponse>(
            `/api/predefined-queries?search=${encodeURIComponent(search)}`,
          ),
          "shared query list",
        ),
      favorite: async (queryId: number, isFavorite: boolean) =>
        requireResponse(
          await request<{ id: number; is_favorite: boolean }>(
            `/api/predefined-queries/${queryId}/favorite`,
            {
              method: "PATCH",
              body: { is_favorite: isFavorite },
            },
          ),
          "shared query favorite",
        ),
      create: async (input: PredefinedWriteInput) =>
        request<{ status: string }>("/api/predefined-queries", {
          method: "POST",
          body: input,
        }),
      update: async (queryId: number, input: PredefinedWriteInput) =>
        request<{ status: string }>(`/api/predefined-queries/${queryId}`, {
          method: "PATCH",
          body: input,
        }),
      delete: async (queryId: number) =>
        request<{ status: string }>(`/api/predefined-queries/${queryId}`, {
          method: "DELETE",
        }),
      execute: async (
        queryId: number,
        parameters: Record<string, unknown>,
      ) =>
        requireResponse(
          await request<PredefinedExecutionResponse>(
            `/api/predefined-queries/${queryId}/execute`,
            {
              method: "POST",
              body: { parameters },
            },
          ),
          "shared query execution",
        ),
    },
    admin: {
      listUsers: async () =>
        requireResponse(
          await request<AdminProfileListResponse>("/api/admin/users"),
          "admin user list",
        ),
      updateStatus: async (userId: string, status: AdminStatus) =>
        requireResponse(
          await request<{ id: string; status: AdminStatus }>(
            `/api/admin/users/${encodeURIComponent(userId)}/status`,
            {
              method: "PATCH",
              body: { status },
            },
          ),
          "admin status update",
        ),
      updateRole: async (userId: string, role: AdminRole) =>
        requireResponse(
          await request<{ id: string; role: AdminRole }>(
            `/api/admin/users/${encodeURIComponent(userId)}/role`,
            {
              method: "PATCH",
              body: { role },
            },
          ),
          "admin role update",
        ),
    },
    schema: {
      sync: async () =>
        requireResponse(
          await request<SchemaSyncResponse>("/api/schema/sync", {
            method: "POST",
          }),
          "schema synchronization",
        ),
    },
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;
