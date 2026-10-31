export type UserRole = "user" | "dev" | "dba" | "admin";
export type ProfileStatus = "pending" | "approved" | "rejected" | "disabled";

export interface Profile {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  status: ProfileStatus;
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

export interface MessageResponse {
  message: string;
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
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;
