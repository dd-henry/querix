import { describe, expect, it, vi } from "vitest";

import { ApiError, createApiClient } from "./client";

function response(body: unknown, status = 200) {
  return new Response(
    body === undefined ? undefined : JSON.stringify(body),
    {
      status,
      headers: body === undefined
        ? undefined
        : { "Content-Type": "application/json" },
    },
  );
}

describe("createApiClient", () => {
  it("uses credentialed JSON requests and returns typed auth data", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(
      response({
        id: "user-1",
        email: "user@example.com",
        name: "User",
        role: "user",
        status: "approved",
      }),
    );
    const client = createApiClient({ fetchImpl });

    const profile = await client.auth.login({
      email: "user@example.com",
      password: "password",
    });

    expect(profile?.id).toBe("user-1");
    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/auth/login",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        body: JSON.stringify({
          email: "user@example.com",
          password: "password",
        }),
      }),
    );
  });

  it("accepts empty successful responses", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(response(undefined, 204));
    const client = createApiClient({ fetchImpl });

    const result = await client.auth.logout();

    expect(result).toBeUndefined();
  });

  it("normalizes validation errors with code and message", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(
      response(
        {
          error: {
            code: "validation_error",
            message: "Invalid request.",
          },
        },
        422,
      ),
    );
    const client = createApiClient({ fetchImpl });

    await expect(
      client.auth.login({ email: "", password: "" }),
    ).rejects.toEqual(
      new ApiError("validation_error", "Invalid request.", 422),
    );
  });

  it("calls the unauthorized callback for a 401 response", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(
      response(
        {
          error: {
            code: "auth_required",
            message: "Authentication required.",
          },
        },
        401,
      ),
    );
    const onUnauthorized = vi.fn();
    const client = createApiClient({ fetchImpl, onUnauthorized });

    await expect(client.auth.me()).rejects.toMatchObject({
      code: "auth_required",
      status: 401,
    });
    expect(onUnauthorized).toHaveBeenCalledOnce();
  });

  it("reports malformed error payloads without hiding the status", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(
      response({ detail: "legacy error" }, 500),
    );
    const client = createApiClient({ fetchImpl });

    await expect(client.auth.me()).rejects.toEqual(
      new ApiError(
        "invalid_error_response",
        "The API returned an invalid error response.",
        500,
      ),
    );
  });
});
