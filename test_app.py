from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import core.auth
import core.prompter
import core.translator
import database.conversations
import database.postgres
import database.predefined_queries
import database.query_history
import database.users


APP_PATH = Path(__file__).parent / "app.py"
USER_ID = "user-1"


class FakeConversationRepository:
    def __init__(self):
        self.sessions = []
        self.messages = {}
        self.listed_users = []
        self.expired_count = 0
        self.context = []
        self.context_calls = []
        self.create_error = None
        self.load_error = None

    def initialize(self):
        return None

    def list_sessions_with_expired_count(self, user_id):
        self.listed_users.append(user_id)
        return [
            session for session in self.sessions if session["user_id"] == user_id
        ], self.expired_count

    def create_with_user_message(self, user_id, session_id, request_id, prompt):
        if self.create_error:
            raise self.create_error
        self.sessions.append(
            {
                "id": session_id,
                "user_id": user_id,
                "title": prompt[:80],
                "is_favorite": False,
                "last_activity": datetime.now(timezone.utc),
            }
        )
        self.messages[session_id] = [
            {
                "request_id": request_id,
                "role": "user",
                "content": prompt,
                "sql": None,
                "error": None,
                "metadata": {},
            }
        ]

    def append_message(
        self, user_id, session_id, request_id, role, content, sql=None,
        error=None, metadata=None
    ):
        records = self.messages.setdefault(session_id, [])
        if not any(
            str(row["request_id"]) == str(request_id) and row["role"] == role
            for row in records
        ):
            records.append(
                {
                    "request_id": request_id,
                    "role": role,
                    "content": content,
                    "sql": sql,
                    "error": error,
                    "metadata": metadata or {},
                }
            )

    def update_assistant_message(
        self, user_id, session_id, request_id, content, sql=None,
        error=None, metadata=None
    ):
        for row in self.messages.get(session_id, []):
            if (
                str(row["request_id"]) == str(request_id)
                and row["role"] == "assistant"
            ):
                row.update(
                    content=content,
                    sql=sql,
                    error=error,
                    metadata=metadata or {},
                )
                return
        raise AssertionError("Retry must update an existing assistant turn.")

    def get_messages(self, user_id, session_id):
        if self.load_error:
            raise self.load_error
        session = next(
            (
                item for item in self.sessions
                if item["id"] == session_id and item["user_id"] == user_id
            ),
            None,
        )
        if session is None:
            return []
        return list(self.messages.get(session_id, []))

    def get_context(
        self, user_id, session_id, limit=6, exclude_request_id=None
    ):
        self.context_calls.append(
            (user_id, session_id, limit, exclude_request_id)
        )
        return list(self.context[-limit * 2 :]) if limit else []

    def set_favorite(self, user_id, session_id, favorite):
        for session in self.sessions:
            if session["id"] == session_id and session["user_id"] == user_id:
                session["is_favorite"] = favorite
                return

    def delete(self, user_id, session_id):
        self.sessions = [
            session
            for session in self.sessions
            if not (
                session["id"] == session_id
                and session["user_id"] == user_id
            )
        ]
        self.messages.pop(session_id, None)


class FakeHistoryRepository:
    def __init__(self):
        self.records = []
        self.rows = []
        self.listed_users = []

    def initialize(self):
        return None

    def list(self, user_id):
        self.listed_users.append(user_id)
        return self.rows

    def record(
        self, user_id, prompt, sql, source="chat", parameters=None,
        session_id=None
    ):
        self.records.append(
            {
                "user_id": user_id,
                "prompt": prompt,
                "sql": sql,
                "source": source,
                "parameters": parameters or {},
                "session_id": session_id,
            }
        )

    def set_pinned(self, *args):
        return None

    def delete(self, *args):
        return None


class FakeCatalogRepository:
    def __init__(self):
        self.rows = []

    def initialize(self):
        return None

    def list(self, user_id):
        return self.rows

    @staticmethod
    def validate_query(sql, parameters):
        normalized = sql.strip().rstrip(";").strip()
        if (
            not normalized.upper().startswith(("SELECT ", "WITH "))
            or ";" in normalized
            or not isinstance(parameters, list)
        ):
            raise ValueError("Only a single read query is allowed.")
        return normalized


class FakeTranslator:
    def __init__(self):
        self.responses = [{"sql": "SELECT 1", "grafico": None}]
        self.calls = []

    def translate_to_sql(self, prompt, conversation_context=None):
        self.calls.append((prompt, conversation_context))
        response = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture
def chat_app(monkeypatch):
    st.cache_resource.clear()
    st.cache_data.clear()

    services = SimpleNamespace(
        auth=MagicMock(),
        db=MagicMock(),
        users=MagicMock(),
        conversations=FakeConversationRepository(),
        history=FakeHistoryRepository(),
        catalog=FakeCatalogRepository(),
        translator=FakeTranslator(),
        progress_labels=[],
    )
    services.auth.sign_in.side_effect = RuntimeError("Credenciais inválidas.")
    services.auth.sign_up.side_effect = RuntimeError("Cadastro indisponível.")
    services.db.get_schema_info.return_value = "Tabela clientes."
    services.db.execute_query.return_value = pd.DataFrame({"total": [1]})
    services.db.execute_read_only_query.return_value = pd.DataFrame({"total": [2]})
    services.users.get_profile.return_value = {
        "id": USER_ID,
        "email": "analista@example.com",
        "name": "Analista",
        "role": "user",
        "status": "approved",
    }
    services.users.list_profiles.return_value = []
    catalog_factory = lambda _db: services.catalog
    catalog_factory.validate_query = FakeCatalogRepository.validate_query

    @contextmanager
    def capture_spinner(label):
        services.progress_labels.append(label)
        yield

    monkeypatch.setattr(st, "spinner", capture_spinner)

    monkeypatch.setattr(core.auth, "SupabaseAuth", lambda: services.auth)
    monkeypatch.setattr(core.prompter, "Prompter", lambda: MagicMock(
        build_system_prompt=MagicMock(return_value="System prompt")
    ))
    monkeypatch.setattr(database.postgres, "PostgresAdapter", lambda: services.db)
    monkeypatch.setattr(database.users, "UserRepository", lambda _db: services.users)
    monkeypatch.setattr(
        database.conversations,
        "ConversationRepository",
        lambda _db: services.conversations,
    )
    monkeypatch.setattr(
        database.query_history,
        "QueryHistoryRepository",
        lambda _db: services.history,
    )
    monkeypatch.setattr(
        database.predefined_queries,
        "PredefinedQueryRepository",
        catalog_factory,
    )
    monkeypatch.setattr(
        core.translator,
        "Translator",
        lambda **_kwargs: services.translator,
    )

    app = AppTest.from_file(str(APP_PATH))
    app.run()
    app.session_state["auth_user"] = {"id": USER_ID, "email": "analista@example.com"}
    app.run()
    yield app, services
    st.cache_resource.clear()
    st.cache_data.clear()


def _click(app, label, key=None):
    button = next(
        (
            item for item in app.button
            if item.label == label and (key is None or item.key == key)
        ),
        None,
    )
    if button is None:
        raise AssertionError(
            f"Button not found: {label!r} ({key!r}); "
            f"buttons={[(item.label, item.key) for item in app.button]}; "
            f"expanders={[item.label for item in app.expander]}; "
            f"errors={[item.value for item in app.error]}; "
            f"exceptions={[item.message for item in app.exception]}"
        )
    button.click().run()


def _submit_prompt(app, prompt):
    app.chat_input[0].set_value(prompt).run()


def _seed_session(services, session_id, user_id=USER_ID, title="Conversa"):
    services.conversations.sessions.append(
        {
            "id": session_id,
            "user_id": user_id,
            "title": title,
            "is_favorite": False,
            "last_activity": datetime.now(timezone.utc),
        }
    )
    services.conversations.messages[session_id] = []


def test_approved_user_starts_in_blank_draft_and_lists_only_own_sessions(chat_app):
    app, services = chat_app

    assert app.session_state["active_conversation_id"] is None
    assert app.session_state["messages"] == []
    assert services.conversations.listed_users == [USER_ID]
    assert len(app.chat_input) == 1


def test_legacy_streamlit_state_starts_as_a_blank_conversation(chat_app):
    app, _services = chat_app
    del app.session_state["active_conversation_id"]
    app.session_state["messages"] = [
        {"role": "user", "content": "Conteúdo da sessão anterior."}
    ]
    app.session_state["pending_sql"] = "SELECT stale"

    app.run()

    assert app.session_state["active_conversation_id"] is None
    assert app.session_state["messages"] == []
    assert "pending_sql" not in app.session_state


def test_storage_failure_is_reported_without_starting_translation(chat_app):
    app, services = chat_app
    services.conversations.create_error = RuntimeError("Banco indisponível.")

    _submit_prompt(app, "Minha pergunta.")

    assert services.translator.calls == []
    assert app.session_state["active_conversation_id"] is None
    assert any("A pergunta não foi salva" in item.value for item in app.error)


def test_new_prompt_is_saved_once_and_sql_review_is_default(chat_app):
    app, services = chat_app

    _submit_prompt(app, "Quantos clientes?")

    session_id = app.session_state["active_conversation_id"]
    records = services.conversations.messages[session_id]
    assert [record["role"] for record in records] == ["user", "assistant"]
    assert records[0]["content"] == "Quantos clientes?"
    assert records[1]["sql"] == "SELECT 1"
    assert [item.value for item in app.code] == ["SELECT 1"]
    assert services.db.execute_query.call_count == 0
    assert len(app.chat_message) == 2
    assert {
        "Salvando sua pergunta...",
        "Traduzindo sua pergunta para SQL...",
        "Salvando a resposta...",
    } <= set(services.progress_labels)
    app.run()
    assert len(services.conversations.messages[session_id]) == 2
    assert len(services.translator.calls) == 1


def test_resumed_prompt_uses_no_more_than_six_completed_turns(chat_app):
    app, services = chat_app
    _seed_session(services, "session-old")
    app.session_state["active_conversation_id"] = "session-old"
    services.conversations.context = [
        {"role": role, "content": f"{role}-{index}"}
        for index in range(12)
        for role in ("user", "assistant")
    ][-12:]
    app.run()

    _submit_prompt(app, "Pergunta nova?")

    prompt, context = services.translator.calls[-1]
    assert prompt == "Pergunta nova?"
    assert len(context) == 12
    assert services.conversations.context_calls[-1][2] == 6


def test_saved_sessions_are_grouped_by_recency(chat_app):
    app, services = chat_app
    now = datetime.now(timezone.utc)
    for session_id, age_days in (
        ("today", 0),
        ("yesterday", 1),
        ("week", 5),
        ("month", 20),
        ("older", 50),
    ):
        _seed_session(services, session_id, title=session_id)
        services.conversations.sessions[-1]["last_activity"] = now - timedelta(
            days=age_days
        )

    app.run()

    labels = {item.label for item in app.expander}
    assert {"Hoje", "Ontem", "Últimos 7 dias", "Últimos 30 dias", "Mais antigas"} <= labels


def test_resuming_session_restores_sql_without_fetching_result_rows(chat_app):
    app, services = chat_app
    _seed_session(services, "session-saved")
    services.conversations.messages["session-saved"] = [
        {
            "request_id": "turn-saved",
            "role": "user",
            "content": "Mostre o total.",
            "sql": None,
            "error": None,
            "metadata": {},
        },
        {
            "request_id": "turn-saved",
            "role": "assistant",
            "content": "Resultado salvo como SQL.",
            "sql": "SELECT 42",
            "error": None,
            "metadata": {},
        },
    ]
    app.run()

    _click(app, "Conversa", key="open_session_session-saved")

    assert app.session_state["active_conversation_id"] == "session-saved"
    assert app.session_state["messages"][1]["sql"] == "SELECT 42"
    assert "df" not in app.session_state["messages"][1]
    services.db.execute_query.assert_not_called()


def test_new_conversation_action_clears_the_active_transcript(chat_app):
    app, services = chat_app
    _seed_session(services, "session-current")
    app.session_state["active_conversation_id"] = "session-current"
    app.session_state["messages"] = [
        {"role": "user", "content": "Pergunta antiga."}
    ]
    app.run()

    _click(app, "＋ Nova conversa", key="new_conversation")

    assert app.session_state["active_conversation_id"] is None
    assert app.session_state["messages"] == []
    assert len(app.chat_input) == 1


def test_conversation_load_failure_is_reported_without_switching(chat_app):
    app, services = chat_app
    _seed_session(services, "session-private")
    services.conversations.load_error = RuntimeError("Banco indisponível.")
    app.run()

    _click(app, "Conversa", key="open_session_session-private")

    assert app.session_state["active_conversation_id"] is None
    assert any("Não foi possível carregar a conversa" in item.value for item in app.error)


def test_foreign_sessions_are_not_rendered_or_opened(chat_app):
    app, services = chat_app
    _seed_session(services, "private-to-other", user_id="user-2", title="Segredo")

    app.run()

    assert services.conversations.listed_users[-1] == USER_ID
    assert "Segredo" not in [item.label for item in app.button]
    assert app.session_state["active_conversation_id"] is None


def test_missing_active_session_cancels_its_pending_action(chat_app):
    app, _services = chat_app
    app.session_state["active_conversation_id"] = "deleted-session"
    app.session_state["messages"] = [
        {"role": "user", "content": "Pergunta antiga."}
    ]
    app.session_state["pending_action"] = {
        "kind": "execute",
        "sql": "SELECT 1",
    }

    app.run()

    assert app.session_state["active_conversation_id"] is None
    assert app.session_state["pending_action"] is None
    assert any("ação pendente foi cancelada" in item.value for item in app.error)
    assert app.session_state["messages"] == []


def test_favorite_action_updates_the_owned_session(chat_app):
    app, services = chat_app
    _seed_session(services, "session-favorite")
    app.run()

    _click(app, "☆", key="favorite_session_session-favorite")

    assert services.conversations.sessions[0]["is_favorite"] is True


def test_session_deletion_requires_confirmation_and_clears_active_chat(chat_app):
    app, services = chat_app
    _seed_session(services, "session-delete")
    app.session_state["active_conversation_id"] = "session-delete"
    app.session_state["messages"] = [
        {"role": "user", "content": "Old question"}
    ]
    app.run()

    _click(app, "Excluir", key="delete_session_session-delete")

    assert services.conversations.sessions
    _click(app, "Confirmar exclusão", key="confirm_delete_session")

    assert services.conversations.sessions == []
    assert app.session_state["active_conversation_id"] is None
    assert app.session_state["messages"] == []


def test_reviewed_query_runs_once_and_is_linked_to_active_session(chat_app):
    app, services = chat_app

    _submit_prompt(app, "Some um.")
    session_id = app.session_state["active_conversation_id"]
    assert services.db.execute_query.call_count == 0

    _click(app, "Executar SQL revisado")

    assert services.db.execute_query.call_count == 1
    assert len(services.history.records) == 1
    assert services.history.records[0]["session_id"] == session_id
    assert len(app.session_state["messages"]) == 2
    assert app.session_state["messages"][1]["df"].to_dict("records") == [
        {"total": 1}
    ]
    assert all(
        "df" not in message
        for message in services.conversations.messages[session_id]
    )
    assert "Executando consulta no banco..." in services.progress_labels


def test_direct_execution_remains_available_when_review_is_disabled(chat_app):
    app, services = chat_app
    app.toggle[0].set_value(False).run()

    _submit_prompt(app, "Some os valores.")

    assert services.db.execute_query.call_count == 1
    assert app.session_state["pending_review"] is None
    assert app.session_state["messages"][1]["df"].to_dict("records") == [
        {"total": 1}
    ]


def test_translation_retry_replaces_the_assistant_turn(chat_app):
    app, services = chat_app
    services.translator.responses = [
        RuntimeError("Ollama indisponível."),
        {"sql": "SELECT 2", "grafico": None},
    ]

    _submit_prompt(app, "Tente traduzir.")
    session_id = app.session_state["active_conversation_id"]
    assert len(services.conversations.messages[session_id]) == 2
    failed_message = services.conversations.messages[session_id][1]
    assert failed_message["error"] == "Ollama indisponível."
    assert any("Ollama indisponível." in item.value for item in app.error)

    _click(app, "Tentar novamente")

    records = services.conversations.messages[session_id]
    assert len(records) == 2
    assert records[1]["sql"] == "SELECT 2"
    assert records[1]["error"] is None
    assert services.conversations.context_calls[-1][3] == failed_message["request_id"]


def test_failed_read_query_can_be_retried_only_by_user_action(chat_app):
    app, services = chat_app
    services.db.execute_query.side_effect = [
        RuntimeError("Consulta temporariamente indisponível."),
        pd.DataFrame({"total": [2]}),
    ]

    _submit_prompt(app, "Consulte o total.")
    _click(app, "Executar SQL revisado")
    session_id = app.session_state["active_conversation_id"]
    assert services.db.execute_query.call_count == 1
    assert services.conversations.messages[session_id][1]["error"]
    assert any(
        "Consulta temporariamente indisponível." in item.value
        for item in app.error
    )
    assert app.session_state["messages"][1]["retryable"] is True

    _click(app, "Tentar novamente")

    assert services.db.execute_query.call_count == 1
    services.db.execute_read_only_query.assert_called_once()
    assert len(services.conversations.messages[session_id]) == 2
    assert services.conversations.messages[session_id][1]["error"] is None
    assert len(services.history.records) == 1


def test_mutating_sql_does_not_offer_a_query_retry(chat_app):
    app, services = chat_app
    services.db.execute_query.side_effect = RuntimeError("Operação bloqueada.")
    _seed_session(services, "session-mutation")
    turn = {
        "session_id": "session-mutation",
        "request_id": "turn-mutation",
        "prompt": "Atualize o valor.",
    }
    services.conversations.messages["session-mutation"] = [
        {
            "request_id": "turn-mutation",
            "role": "user",
            "content": "Atualize o valor.",
        },
    ]
    app.session_state["active_conversation_id"] = "session-mutation"
    app.session_state["messages"] = [
        {"request_id": "turn-mutation", "role": "user", "content": turn["prompt"]}
    ]
    app.session_state["pending_action"] = {
        "kind": "execute",
        "turn": turn,
        "sql": "DELETE FROM clientes",
        "source": "chat",
        "parameters": {},
        "retry": False,
    }
    app.run()

    assert "Tentar novamente" not in [item.label for item in app.button]
    assert services.db.execute_read_only_query.call_count == 0
    assert services.conversations.messages["session-mutation"][1]["metadata"][
        "retryable"
    ] is False


def test_login_failure_is_reported_without_losing_the_login_view(monkeypatch):
    st.cache_resource.clear()
    st.cache_data.clear()
    auth = MagicMock()
    auth.sign_in.side_effect = RuntimeError("Credenciais inválidas.")
    progress_labels = []

    @contextmanager
    def capture_spinner(label):
        progress_labels.append(label)
        yield

    monkeypatch.setattr(core.auth, "SupabaseAuth", lambda: auth)
    monkeypatch.setattr(database.postgres, "PostgresAdapter", MagicMock)
    monkeypatch.setattr(st, "spinner", capture_spinner)
    monkeypatch.setattr(
        database.users,
        "UserRepository",
        lambda _db: MagicMock(initialize=MagicMock()),
    )
    app = AppTest.from_file(str(APP_PATH)).run()
    app.text_input[0].set_value("analista@example.com")
    app.text_input[1].set_value("senha-incorreta")
    _click(app, "Entrar")

    assert any("Não foi possível entrar" in item.value for item in app.error)
    assert {item.label for item in app.tabs} == {"Entrar", "Criar conta"}
    assert "Validando credenciais..." in progress_labels


def test_successful_login_opens_the_approved_chat(chat_app):
    app, services = chat_app
    services.auth.sign_in.side_effect = None
    services.auth.sign_in.return_value = (
        SimpleNamespace(id=USER_ID, email="analista@example.com"),
        object(),
    )
    app.session_state["auth_user"] = None
    app.run()
    app.text_input[0].set_value("analista@example.com")
    app.text_input[1].set_value("senha-correta")

    _click(app, "Entrar")

    assert app.session_state["auth_user"]["id"] == USER_ID
    assert len(app.chat_input) == 1
    assert not app.error


def test_user_and_admin_keep_their_role_gated_tools(chat_app):
    app, services = chat_app
    assert "Administrar usuários" not in [
        item.label for item in app.expander
    ]

    services.users.get_profile.return_value = {
        "id": USER_ID,
        "email": "admin@example.com",
        "name": "Admin",
        "role": "admin",
        "status": "approved",
    }
    app.run()

    assert "Administrar usuários" in [
        item.label for item in app.expander
    ]


def test_developer_can_manage_shared_queries_but_not_users(chat_app):
    app, services = chat_app
    services.users.get_profile.return_value = {
        "id": USER_ID,
        "email": "dev@example.com",
        "name": "Developer",
        "role": "dev",
        "status": "approved",
    }

    app.run()

    labels = {item.label for item in app.expander}
    assert "Administrar catálogo" in labels
    assert "Administrar usuários" not in labels


def test_existing_query_tools_remain_grouped_in_the_sidebar(chat_app):
    app, _services = chat_app

    assert {"Histórico de consultas", "Consultas compartilhadas"} <= {
        item.label for item in app.expander
    }


def test_opening_history_reports_expired_session_cleanup(chat_app):
    app, services = chat_app
    services.conversations.expired_count = 3

    app.run()

    assert any("3 conversas antigas" in item.value for item in app.toast)


def test_logout_clears_chat_and_pending_state(chat_app):
    app, services = chat_app
    app.session_state["active_conversation_id"] = "session-current"
    app.session_state["messages"] = [
        {"role": "user", "content": "Conteúdo privado."}
    ]
    app.session_state["pending_action"] = {"kind": "translate"}

    _click(app, "Sair", key="logout")

    assert services.auth.sign_out.call_count == 1
    assert app.session_state["auth_user"] is None
    assert "messages" not in app.session_state
    assert "pending_action" not in app.session_state
