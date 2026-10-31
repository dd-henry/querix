import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { App } from "./App";

describe("App", () => {
  it("renders the initial web shell", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: "Converse com seus dados" }),
    ).toBeInTheDocument();
  });
});
