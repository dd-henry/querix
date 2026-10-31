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
    };
    render(<App client={client} />);

    await expect(
      screen.findByRole("heading", { name: "Converse com seus dados" }),
    ).resolves.toBeInTheDocument();
  });
});
