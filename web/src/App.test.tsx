import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { type ApiClient } from "./api/client";
import { App } from "./App";

describe("App", () => {
  it("renders the initial web shell", async () => {
    const client: ApiClient = {
      auth: {
        me: () =>
          Promise.resolve({
            id: "user-1",
            email: "user@example.com",
            name: "User",
            role: "user",
            status: "approved",
          }),
        login: () => Promise.reject(new Error("not used")),
        signup: () => Promise.reject(new Error("not used")),
        logout: () => Promise.resolve({ message: "Logged out." }),
      },
      conversations: {
        list: () => Promise.resolve({ groups: [], expired_count: 0 }),
        get: () => Promise.reject(new Error("not used")),
        create: () => Promise.reject(new Error("not used")),
        favorite: () => Promise.reject(new Error("not used")),
        delete: () => Promise.resolve(undefined),
      },
      chat: {
        translate: () => Promise.reject(new Error("not used")),
        execute: () => Promise.reject(new Error("not used")),
        retry: () => Promise.reject(new Error("not used")),
      },
      history: {
        list: () => Promise.resolve({ records: [] }),
        pin: () => Promise.reject(new Error("not used")),
        delete: () => Promise.reject(new Error("not used")),
        rerun: () => Promise.reject(new Error("not used")),
      },
      predefined: {
        list: () => Promise.resolve({ queries: [] }),
        favorite: () => Promise.reject(new Error("not used")),
        create: () => Promise.reject(new Error("not used")),
        update: () => Promise.reject(new Error("not used")),
        delete: () => Promise.reject(new Error("not used")),
        execute: () => Promise.reject(new Error("not used")),
      },
    };
    render(<App client={client} />);

    await expect(
      screen.findByRole("heading", { name: "Converse com seus dados" }),
    ).resolves.toBeInTheDocument();
  });
});
