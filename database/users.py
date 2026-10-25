from database.postgres import PostgresAdapter


VALID_ROLES = {"user", "dev", "admin"}
VALID_STATUSES = {"pending", "approved", "rejected", "disabled"}


class UserRepository:
    """Perfis e decisões administrativas complementares ao Supabase Auth."""

    def __init__(self, db: PostgresAdapter):
        self.db = db

    def initialize(self):
        self.db.execute_command(
            """
            CREATE TABLE IF NOT EXISTS public.profiles (
                id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
                email TEXT NOT NULL,
                name TEXT NOT NULL DEFAULT '',
                role TEXT NOT NULL DEFAULT 'user'
                    CHECK (role IN ('user', 'dev', 'admin')),
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'approved', 'rejected', 'disabled')),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                approved_at TIMESTAMPTZ,
                approved_by UUID REFERENCES auth.users(id),
                disabled_at TIMESTAMPTZ
            )
            """
        )

    def create_pending_profile(self, user_id, email, name):
        self.db.execute_command(
            """
            INSERT INTO public.profiles (id, email, name)
            VALUES (:id, :email, :name)
            ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email, name = EXCLUDED.name
            """,
            {"id": str(user_id), "email": email, "name": name},
        )

    def get_profile(self, user_id):
        result = self.db.execute_query(
            "SELECT id, email, name, role, status FROM public.profiles WHERE id = :id",
            {"id": str(user_id)},
        )
        if result.empty:
            return None
        return result.iloc[0].to_dict()

    def list_profiles(self):
        result = self.db.execute_query(
            """
            SELECT id, email, name, role, status, created_at, approved_at, disabled_at
            FROM public.profiles
            ORDER BY created_at DESC
            """
        )
        return result.to_dict("records")

    def set_status(self, target_id, status, admin_id):
        if status not in VALID_STATUSES:
            raise ValueError("Status de usuário inválido.")
        if str(target_id) == str(admin_id) and status != "approved":
            raise ValueError("O admin atual não pode bloquear ou rejeitar a própria conta.")
        if status != "approved" and self._is_last_admin(target_id):
            raise ValueError("O último admin não pode ser bloqueado ou rejeitado.")
        if status == "approved":
            self.db.execute_command(
                """
                UPDATE public.profiles
                SET status = 'approved', approved_at = NOW(), approved_by = :admin_id,
                    disabled_at = NULL
                WHERE id = :target_id
                """,
                {"target_id": str(target_id), "admin_id": str(admin_id)},
            )
            return
        self.db.execute_command(
            """
            UPDATE public.profiles
            SET status = :status,
                disabled_at = CASE WHEN :status = 'disabled' THEN NOW() ELSE NULL END
            WHERE id = :target_id
            """,
            {"target_id": str(target_id), "status": status},
        )

    def set_role(self, target_id, role, admin_id):
        if role not in VALID_ROLES:
            raise ValueError("Papel de usuário inválido.")
        if str(target_id) == str(admin_id) and role != "admin":
            raise ValueError("O admin atual não pode remover o próprio papel de admin.")
        if role != "admin" and self._is_last_admin(target_id):
            raise ValueError("O último admin não pode perder o papel de admin.")
        self.db.execute_command(
            "UPDATE public.profiles SET role = :role WHERE id = :target_id",
            {"target_id": str(target_id), "role": role},
        )

    def _is_last_admin(self, target_id):
        result = self.db.execute_query(
            """
            SELECT COUNT(*) AS admin_count
            FROM public.profiles
            WHERE role = 'admin' AND status = 'approved'
              AND id = :target_id
            """,
            {"target_id": str(target_id)},
        )
        target_is_admin = int(result.iloc[0]["admin_count"]) == 1
        if not target_is_admin:
            return False
        count = self.db.execute_query(
            "SELECT COUNT(*) AS admin_count FROM public.profiles WHERE role = 'admin' AND status = 'approved'"
        )
        return int(count.iloc[0]["admin_count"]) <= 1

    def bootstrap_admin(self, email):
        self.db.execute_command(
            """
            UPDATE public.profiles
            SET role = 'admin', status = 'approved', approved_at = NOW()
            WHERE lower(email) = lower(:email)
              AND NOT EXISTS (
                  SELECT 1 FROM public.profiles WHERE role = 'admin'
              )
            """,
            {"email": email.strip()},
        )
