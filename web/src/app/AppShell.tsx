import { useState, type ReactNode } from "react";

import type { Profile } from "../api/client";

type SidebarContent =
  | ReactNode
  | ((closeSidebar: () => void) => ReactNode);

export interface AppShellProps {
  profile: Profile;
  sidebar: SidebarContent;
  chat: ReactNode;
  requestStatus?: string;
  onSignOut: () => void | Promise<void>;
}

export function AppShell({
  profile,
  sidebar,
  chat,
  requestStatus = "",
  onSignOut,
}: AppShellProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const closeSidebar = () => setSidebarOpen(false);
  const sidebarContent =
    typeof sidebar === "function" ? sidebar(closeSidebar) : sidebar;

  return (
    <div className="app-shell app-shell--authenticated">
      <button
        className="app-nav-toggle"
        type="button"
        aria-controls="app-sidebar"
        aria-expanded={sidebarOpen}
        aria-label={sidebarOpen ? "Fechar navegação" : "Abrir navegação"}
        onClick={() => setSidebarOpen((open) => !open)}
      >
        {sidebarOpen ? "Fechar menu" : "Abrir menu"}
      </button>
      <aside
        id="app-sidebar"
        className={`app-sidebar${sidebarOpen ? " is-open" : ""}`}
        aria-label="Navegação principal"
      >
        <div className="app-sidebar__brand">
          <p className="eyebrow">Ask SQL</p>
          <p>{profile.name}</p>
        </div>
        <div className="app-sidebar__content">{sidebarContent}</div>
        <button
          type="button"
          aria-label="Sair"
          onClick={() => {
            closeSidebar();
            void onSignOut();
          }}
        >
          Sair
        </button>
      </aside>
      <main className="app-main" aria-label="Área de chat">
        <header className="app-main__header">
          <div>
            <p className="eyebrow">Conversa</p>
            <h1>Converse com seus dados</h1>
          </div>
          <span aria-label={`Perfil: ${profile.role}`}>{profile.role}</span>
        </header>
        <section className="app-chat" aria-label="Chat">
          {chat}
        </section>
        <div className="app-status" role="status" aria-live="polite">
          {requestStatus}
        </div>
      </main>
    </div>
  );
}
