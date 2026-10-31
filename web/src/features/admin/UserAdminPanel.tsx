import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  type AdminProfile,
  type AdminRole,
  type AdminStatus,
  type ApiClient,
  type ProfileStatus,
  type UserRole,
} from "../../api/client";

export interface UserAdminPanelProps {
  client: ApiClient;
  role: UserRole;
}

interface AdminDraft {
  status: ProfileStatus;
  role: AdminRole;
}

const roleOptions: AdminRole[] = ["user", "dev", "admin"];
const statusOptions: Array<ProfileStatus> = [
  "pending",
  "approved",
  "rejected",
  "disabled",
];

function isAdminStatus(value: ProfileStatus): value is AdminStatus {
  return value !== "pending";
}

function draftsForProfiles(profiles: AdminProfile[]): Record<string, AdminDraft> {
  return profiles.reduce<Record<string, AdminDraft>>((drafts, profile) => {
    drafts[profile.id] = { status: profile.status, role: profile.role };
    return drafts;
  }, {});
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "last_admin_conflict") {
      return `${error.message} Aprove outro administrador antes de remover este acesso.`;
    }
    return error.message;
  }
  return "Não foi possível atualizar o usuário.";
}

export function UserAdminPanel({ client, role }: UserAdminPanelProps) {
  const [profiles, setProfiles] = useState<AdminProfile[]>([]);
  const [drafts, setDrafts] = useState<Record<string, AdminDraft>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [pendingAction, setPendingAction] = useState<string | null>(null);

  const loadProfiles = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await client.admin.listUsers();
      setProfiles(response.profiles);
      setDrafts(draftsForProfiles(response.profiles));
    } catch (loadError: unknown) {
      setError(errorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, [client]);

  useEffect(() => {
    if (role === "admin") {
      void loadProfiles();
    } else {
      setLoading(false);
    }
  }, [loadProfiles, role]);

  if (role !== "admin") {
    return null;
  }

  const updateDraft = (
    userId: string,
    field: keyof AdminDraft,
    value: ProfileStatus | AdminRole,
  ) => {
    setDrafts((current) => ({
      ...current,
      [userId]: { ...current[userId], [field]: value },
    }));
  };

  const handleStatusUpdate = async (profile: AdminProfile) => {
    const status = drafts[profile.id]?.status;
    if (!status || !isAdminStatus(status)) {
      setError("Selecione um status válido para atualizar.");
      return;
    }
    setPendingAction(`status:${profile.id}`);
    setError("");
    setFeedback("");
    try {
      const response = await client.admin.updateStatus(profile.id, status);
      setProfiles((current) =>
        current.map((item) =>
          item.id === profile.id ? { ...item, status: response.status } : item,
        ),
      );
      setFeedback(`Status de ${profile.email} atualizado.`);
    } catch (updateError: unknown) {
      setError(errorMessage(updateError));
    } finally {
      setPendingAction(null);
    }
  };

  const handleRoleUpdate = async (profile: AdminProfile) => {
    const nextRole = drafts[profile.id]?.role;
    if (!nextRole || !roleOptions.includes(nextRole)) {
      setError("Selecione um papel válido para atualizar.");
      return;
    }
    setPendingAction(`role:${profile.id}`);
    setError("");
    setFeedback("");
    try {
      const response = await client.admin.updateRole(profile.id, nextRole);
      setProfiles((current) =>
        current.map((item) =>
          item.id === profile.id ? { ...item, role: response.role } : item,
        ),
      );
      setFeedback(`Papel de ${profile.email} atualizado.`);
    } catch (updateError: unknown) {
      setError(errorMessage(updateError));
    } finally {
      setPendingAction(null);
    }
  };

  return (
    <section className="admin-panel" aria-labelledby="admin-panel-title">
      <header className="admin-panel__header">
        <div>
          <p className="eyebrow">Acesso</p>
          <h2 id="admin-panel-title">Administração de usuários</h2>
        </div>
        <button
          type="button"
          onClick={() => void loadProfiles()}
          disabled={loading}
        >
          Atualizar
        </button>
      </header>
      {error ? <p role="alert">{error}</p> : null}
      {feedback ? <p role="status">{feedback}</p> : null}
      {loading ? (
        <p role="status">Carregando usuários...</p>
      ) : profiles.length === 0 ? (
        <p role="status">Nenhum usuário encontrado.</p>
      ) : (
        <ul className="admin-panel__list">
          {profiles.map((profile) => {
            const draft = drafts[profile.id];
            const statusPending = pendingAction === `status:${profile.id}`;
            const rolePending = pendingAction === `role:${profile.id}`;
            return (
              <li key={profile.id} className="admin-panel__item">
                <div>
                  <h3>{profile.name || profile.email}</h3>
                  <p>{profile.email}</p>
                </div>
                <div className="admin-panel__control">
                  <label htmlFor={`admin-status-${profile.id}`}>
                    Status de {profile.email}
                  </label>
                  <select
                    id={`admin-status-${profile.id}`}
                    value={draft?.status ?? profile.status}
                    onChange={(event) =>
                      updateDraft(
                        profile.id,
                        "status",
                        event.target.value as ProfileStatus,
                      )
                    }
                  >
                    {statusOptions.map((option) => (
                      <option
                        key={option}
                        value={option}
                        disabled={option === "pending"}
                      >
                        {option}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    disabled={statusPending || rolePending}
                    onClick={() => void handleStatusUpdate(profile)}
                  >
                    Atualizar status
                  </button>
                </div>
                <div className="admin-panel__control">
                  <label htmlFor={`admin-role-${profile.id}`}>
                    Papel de {profile.email}
                  </label>
                  <select
                    id={`admin-role-${profile.id}`}
                    value={draft?.role ?? profile.role}
                    onChange={(event) =>
                      updateDraft(
                        profile.id,
                        "role",
                        event.target.value as AdminRole,
                      )
                    }
                  >
                    {roleOptions.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    disabled={statusPending || rolePending}
                    onClick={() => void handleRoleUpdate(profile)}
                  >
                    Atualizar papel
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
