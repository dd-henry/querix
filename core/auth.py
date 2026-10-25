import os
from typing import Optional

from dotenv import load_dotenv
from supabase import Client, create_client


class AuthConfigurationError(RuntimeError):
    pass


class SupabaseAuth:
    """Cliente de autenticação usado apenas no backend do Streamlit."""

    def __init__(self, client: Optional[Client] = None):
        load_dotenv()
        if client is not None:
            self.client = client
            return

        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_ANON_KEY")
        if not url or not key:
            raise AuthConfigurationError(
                "Configure SUPABASE_URL e SUPABASE_ANON_KEY no ambiente."
            )
        self.client = create_client(url, key)

    def sign_up(self, email: str, password: str, name: str):
        response = self.client.auth.sign_up({"email": email, "password": password})
        user = response.user
        if user is None:
            raise RuntimeError("O Supabase não retornou o usuário criado.")
        return user, name.strip()

    def sign_in(self, email: str, password: str):
        response = self.client.auth.sign_in_with_password(
            {"email": email, "password": password}
        )
        if response.user is None or response.session is None:
            raise RuntimeError("Login não retornou uma sessão válida.")
        return response.user, response.session

    def sign_out(self):
        self.client.auth.sign_out()
