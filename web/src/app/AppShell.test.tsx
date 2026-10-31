import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Profile } from "../api/client";
import { AppShell } from "./AppShell";

const profile: Profile = {
  id: "user-1",
  email: "user@example.com",
  name: "User",
  role: "admin",
  status: "approved",
};

function renderShell(onSignOut = vi.fn()) {
  render(
    <AppShell
      profile={profile}
      sidebar={
        <nav aria-label="Seções">
          <button type="button">Conversas</button>
          <button type="button">Histórico</button>
          <button type="button">Consultas compartilhadas</button>
          <button type="button">Administração</button>
        </nav>
      }
      chat={<p>Chat slot</p>}
      requestStatus="Pronto"
      onSignOut={onSignOut}
    />,
  );
  return onSignOut;
}

describe("AppShell", () => {
  it("renders one sidebar, one chat region, and an announced status", () => {
    renderShell();

    expect(screen.getAllByRole("complementary")).toHaveLength(1);
    expect(screen.getAllByRole("main")).toHaveLength(1);
    expect(screen.getByRole("region", { name: "Chat" })).toHaveTextContent(
      "Chat slot",
    );
    expect(screen.getByRole("status")).toHaveAttribute(
      "aria-live",
      "polite",
    );
    expect(screen.getByRole("status")).toHaveTextContent("Pronto");
  });

  it("toggles the sidebar with an accessible mobile menu button", () => {
    renderShell();

    const menuButton = screen.getByRole("button", {
      name: "Abrir navegação",
    });
    const sidebar = screen.getByRole("complementary");

    menuButton.focus();
    expect(menuButton).toHaveFocus();
    expect(menuButton).toHaveAttribute("aria-expanded", "false");
    expect(sidebar).not.toHaveClass("is-open");

    fireEvent.click(menuButton);

    expect(
      screen.getByRole("button", { name: "Fechar navegação" }),
    ).toHaveAttribute("aria-expanded", "true");
    expect(sidebar).toHaveClass("is-open");
  });

  it("renders keyboard-operable named navigation actions", () => {
    renderShell();

    for (const name of [
      "Conversas",
      "Histórico",
      "Consultas compartilhadas",
      "Administração",
      "Sair",
    ]) {
      const action = screen.getByRole("button", { name });
      expect(action).toHaveAttribute("type", "button");
      action.focus();
      expect(action).toHaveFocus();
    }
  });

  it("calls sign out and closes the mobile sidebar", () => {
    const onSignOut = renderShell();
    fireEvent.click(
      screen.getByRole("button", { name: "Abrir navegação" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Sair" }));

    expect(onSignOut).toHaveBeenCalledOnce();
    expect(
      screen.getByRole("button", { name: "Abrir navegação" }),
    ).toHaveAttribute("aria-expanded", "false");
  });
});
