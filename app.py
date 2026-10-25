import json
import logging
from datetime import date, datetime, timezone
from uuid import uuid4

import streamlit as st

from components import render_chat_messages
from core.auth import AuthConfigurationError, SupabaseAuth
from core.prompter import Prompter
from core.translator import Translator
from database.conversations import ConversationRepository
from database.postgres import PostgresAdapter
from database.predefined_queries import PredefinedQueryRepository
from database.query_history import QueryHistoryRepository
from database.users import UserRepository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

st.set_page_config(page_title="Ask SQL", layout="wide")
st.markdown(
    """
    <style>
    .stApp { background: #f7f8fa; }
    .block-container { padding-top: 2rem; padding-bottom: 5rem; max-width: 1200px; }
    section[data-testid="stSidebar"] { background: #f0f3f8; }
    .stChatMessage { border: 1px solid #e7eaf0; border-radius: 14px; }
    .stButton > button { border-radius: 9px; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_db_adapter():
    """Cache do adaptador do banco para evitar reconexões desnecessárias."""
    return PostgresAdapter()


@st.cache_resource
def get_auth_service():
    return SupabaseAuth()


@st.cache_resource
def get_user_repository():
    repository = UserRepository(get_db_adapter())
    repository.initialize()
    return repository


@st.cache_resource
def get_conversation_repository():
    repository = ConversationRepository(get_db_adapter())
    repository.initialize()
    return repository


@st.cache_resource(ttl=60)
def get_translator():
    """Cache do tradutor e do prompt de sistema."""
    prompter = Prompter()
    system_prompt = prompter.build_system_prompt(
        live_schema=get_db_adapter().get_schema_info()
    )
    return Translator(system_prompt=system_prompt, model_name="qwen2.5-coder:7b")


@st.cache_resource
def get_predefined_query_repository():
    repository = PredefinedQueryRepository(get_db_adapter())
    repository.initialize()
    return repository


@st.cache_resource
def get_query_history_repository(cache_version=4):
    repository = QueryHistoryRepository(get_db_adapter())
    repository.initialize()
    return repository


@st.cache_data(ttl=15)
def get_predefined_query_rows(_repository, user_name):
    return _repository.list(user_name)


if "auth_user" not in st.session_state:
    st.session_state.auth_user = None

try:
    auth_service = get_auth_service()
    user_repository = get_user_repository()
except AuthConfigurationError as error:
    st.error(str(error))
    st.info("Configure as chaves do Supabase no arquivo .env e recarregue a aplicação.")
    st.stop()
except Exception as error:
    logger.warning("Autenticação indisponível: %s", error)
    st.error("Não foi possível conectar ao serviço de autenticação ou ao banco de perfis.")
    st.stop()


def render_auth_screen():
    st.title("Ask SQL")
    st.caption("Entre para consultar seus dados ou solicite acesso à sua equipe.")
    login_tab, signup_tab = st.tabs(["Entrar", "Criar conta"])

    with login_tab:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar", type="primary"):
                try:
                    with st.spinner("Validando credenciais..."):
                        user, _session = auth_service.sign_in(email.strip(), password)
                    st.session_state.auth_user = {
                        "id": str(user.id),
                        "email": user.email or email.strip(),
                    }
                    st.rerun()
                except Exception as error:
                    logger.warning("Falha no login: %s", error)
                    st.error(f"Não foi possível entrar: {error}")

    with signup_tab:
        with st.form("signup_form"):
            name = st.text_input("Nome completo")
            email = st.text_input("Email", key="signup_email")
            password = st.text_input("Senha", type="password", key="signup_password")
            password_confirmation = st.text_input(
                "Confirmar senha", type="password"
            )
            if st.form_submit_button("Solicitar acesso"):
                if not name.strip() or not email.strip():
                    st.error("Informe nome e email.")
                elif len(password) < 8:
                    st.error("A senha deve ter pelo menos 8 caracteres.")
                elif password != password_confirmation:
                    st.error("As senhas não conferem.")
                else:
                    try:
                        with st.spinner("Enviando solicitação de acesso..."):
                            user, normalized_name = auth_service.sign_up(
                                email.strip(), password, name
                            )
                            user_repository.create_pending_profile(
                                user.id, user.email or email.strip(), normalized_name
                            )
                        st.success(
                            "Cadastro recebido. Confirme seu email e aguarde a aprovação de um admin."
                        )
                    except Exception as error:
                        logger.warning("Falha ao solicitar acesso: %s", error)
                        st.error(f"Não foi possível criar a conta: {error}")


def clear_chat_state():
    for key in (
        "active_conversation_id",
        "messages",
        "pending_action",
        "pending_review",
        "delete_confirmation_id",
        "storage_notice",
        "pending_sql",
        "pending_grafico",
        "pending_prompt",
    ):
        st.session_state.pop(key, None)


if st.session_state.auth_user is None:
    render_auth_screen()
    st.stop()

auth_user = st.session_state.auth_user
profile = user_repository.get_profile(auth_user["id"])
if profile is None:
    st.error("Seu perfil ainda não foi criado. Solicite suporte ao administrador.")
    if st.button("Sair"):
        auth_service.sign_out()
        st.session_state.auth_user = None
        clear_chat_state()
        st.rerun()
    st.stop()

if profile["status"] != "approved":
    status_messages = {
        "pending": "Seu cadastro aguarda aprovação de um administrador.",
        "rejected": "Seu cadastro foi rejeitado. Contate um administrador.",
        "disabled": "Sua conta está desativada. Contate um administrador.",
    }
    st.warning(status_messages.get(profile["status"], "Sua conta não está liberada."))
    if st.button("Sair"):
        auth_service.sign_out()
        st.session_state.auth_user = None
        clear_chat_state()
        st.rerun()
    st.stop()

translator = get_translator()
conversation_repository = None
conversation_error = None
try:
    conversation_repository = get_conversation_repository()
except Exception as error:
    conversation_error = error
    logger.warning("Armazenamento de conversas indisponível: %s", error)

predefined_queries = None
query_history = None
catalog_available = True
try:
    predefined_queries = get_predefined_query_repository()
except Exception as error:
    catalog_available = False
    logger.warning("Catálogo de consultas indisponível: %s", error)
try:
    query_history = get_query_history_repository()
except Exception as error:
    logger.warning("Histórico de consultas indisponível: %s", error)

current_user_id = auth_user["id"]
current_user_email = profile["email"]
current_role = profile["role"]

if "active_conversation_id" not in st.session_state:
    st.session_state.messages = []

for key, default in (
    ("active_conversation_id", None),
    ("messages", []),
    ("pending_action", None),
    ("pending_review", None),
    ("delete_confirmation_id", None),
    ("storage_notice", None),
):
    if key not in st.session_state:
        st.session_state[key] = default

for key in ("pending_sql", "pending_grafico", "pending_prompt"):
    st.session_state.pop(key, None)


def local_message_from_record(record):
    metadata = record.get("metadata") or {}
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    message = {
        "request_id": str(record["request_id"]),
        "role": record["role"],
        "content": record.get("content") or "",
    }
    for field in ("sql", "error"):
        if record.get(field):
            message[field] = record[field]
    if metadata.get("grafico"):
        message["grafico"] = metadata["grafico"]
    if metadata.get("retryable"):
        message["retryable"] = True
        message["retry_kind"] = metadata.get("retry_kind")
        message["parameters"] = metadata.get("parameters") or {}
        message["source"] = metadata.get("source", "chat")
    return message


def grouped_sessions(rows, today=None):
    today = today or datetime.now().astimezone().date()
    groups = {
        "Hoje": [],
        "Ontem": [],
        "Últimos 7 dias": [],
        "Últimos 30 dias": [],
        "Mais antigas": [],
    }
    for row in rows:
        activity = row.get("last_activity")
        if isinstance(activity, str):
            activity = datetime.fromisoformat(activity)
        if isinstance(activity, date) and not isinstance(activity, datetime):
            activity = datetime.combine(activity, datetime.min.time())
        if isinstance(activity, datetime):
            activity = datetime.fromisoformat(activity.isoformat())
        if activity is None:
            age_days = 31
        else:
            if activity.tzinfo is None:
                activity = activity.replace(tzinfo=timezone.utc)
            age_days = (today - activity.astimezone().date()).days
        if age_days <= 0:
            group = "Hoje"
        elif age_days == 1:
            group = "Ontem"
        elif age_days <= 7:
            group = "Últimos 7 dias"
        elif age_days <= 30:
            group = "Últimos 30 dias"
        else:
            group = "Mais antigas"
        groups[group].append(row)
    return groups


def persist_user_turn(prompt):
    if conversation_repository is None:
        st.session_state.storage_notice = (
            "A conversa não foi salva porque o armazenamento está indisponível."
        )
        return None

    session_id = st.session_state.active_conversation_id
    request_id = str(uuid4())
    try:
        with st.spinner("Salvando sua pergunta..."):
            if session_id is None:
                session_id = str(uuid4())
                conversation_repository.create_with_user_message(
                    current_user_id, session_id, request_id, prompt
                )
                st.session_state.active_conversation_id = session_id
            else:
                conversation_repository.append_message(
                    current_user_id, session_id, request_id, "user", prompt
                )
    except Exception as error:
        logger.exception("Não foi possível salvar a mensagem do usuário.")
        st.session_state.storage_notice = (
            f"A pergunta não foi salva; verifique a conexão e tente novamente. ({error})"
        )
        return None

    st.session_state.messages.append(
        {"request_id": request_id, "role": "user", "content": prompt}
    )
    st.session_state.storage_notice = None
    return {
        "session_id": session_id,
        "request_id": request_id,
        "prompt": prompt,
    }


def save_assistant_turn(turn, content, sql=None, error=None, metadata=None, df=None):
    metadata = metadata or {}
    request_id = turn["request_id"]
    session_id = turn["session_id"]
    existing = any(
        message["role"] == "assistant"
        and str(message.get("request_id")) == str(request_id)
        for message in st.session_state.messages
    )
    try:
        if conversation_repository is None:
            raise RuntimeError("Armazenamento de conversas indisponível.")
        with st.spinner("Salvando a resposta..."):
            if existing:
                conversation_repository.update_assistant_message(
                    current_user_id,
                    session_id,
                    request_id,
                    content,
                    sql=sql,
                    error=error,
                    metadata=metadata,
                )
            else:
                conversation_repository.append_message(
                    current_user_id,
                    session_id,
                    request_id,
                    "assistant",
                    content,
                    sql=sql,
                    error=error,
                    metadata=metadata,
                )
        st.session_state.storage_notice = None
        saved = True
    except Exception as save_error:
        logger.exception("Não foi possível salvar a resposta da conversa.")
        st.session_state.storage_notice = (
            f"A resposta não foi salva; verifique a conexão. ({save_error})"
        )
        saved = False

    message = {
        "request_id": request_id,
        "role": "assistant",
        "content": content,
    }
    if sql:
        message["sql"] = sql
    if error:
        message["error"] = error
    if df is not None:
        message["df"] = df
    if metadata.get("grafico"):
        message["grafico"] = metadata["grafico"]
    if metadata.get("retryable"):
        message["retryable"] = True
        message["retry_kind"] = metadata.get("retry_kind")
        message["parameters"] = metadata.get("parameters") or {}
        message["source"] = metadata.get("source", "chat")
    if not saved:
        message["not_saved"] = True

    for index, previous in enumerate(st.session_state.messages):
        if (
            previous["role"] == "assistant"
            and str(previous.get("request_id")) == str(request_id)
        ):
            st.session_state.messages[index] = message
            break
    else:
        st.session_state.messages.append(message)
    return saved


def add_query_action(prompt, sql, source="chat", parameters=None):
    turn = persist_user_turn(prompt)
    if turn is None:
        return False
    st.session_state.pending_review = None
    st.session_state.pending_action = {
        "kind": "execute",
        "turn": turn,
        "sql": sql,
        "source": source,
        "parameters": parameters or {},
        "grafico": None,
        "retry": False,
    }
    return True


def open_conversation(session_id, rows):
    if not any(str(row["id"]) == str(session_id) for row in rows):
        st.sidebar.error("Esta conversa não está disponível para sua conta.")
        return
    try:
        records = conversation_repository.get_messages(current_user_id, session_id)
    except Exception as error:
        logger.exception("Não foi possível carregar a conversa.")
        st.sidebar.error(f"Não foi possível carregar a conversa: {error}")
        return
    st.session_state.active_conversation_id = str(session_id)
    st.session_state.messages = [
        local_message_from_record(record) for record in records
    ]
    st.session_state.pending_action = None
    st.session_state.pending_review = None
    st.session_state.storage_notice = None
    st.rerun()


def render_conversation_sidebar():
    st.sidebar.subheader("Conversas")
    if st.sidebar.button(
        "＋ Nova conversa", key="new_conversation", use_container_width=True
    ):
        st.session_state.active_conversation_id = None
        st.session_state.messages = []
        st.session_state.pending_action = None
        st.session_state.pending_review = None
        st.session_state.delete_confirmation_id = None
        st.session_state.storage_notice = None
        st.rerun()

    if conversation_repository is None:
        st.sidebar.error(
            "Histórico indisponível. Verifique a conexão com o banco antes de enviar perguntas."
        )
        return []

    try:
        sessions, expired_count = (
            conversation_repository.list_sessions_with_expired_count(current_user_id)
        )
    except Exception as error:
        logger.exception("Não foi possível carregar o histórico de conversas.")
        st.sidebar.error(f"Não foi possível carregar conversas: {error}")
        return []

    if expired_count:
        noun = "conversa antiga" if expired_count == 1 else "conversas antigas"
        verb = "foi removida" if expired_count == 1 else "foram removidas"
        st.toast(f"{expired_count} {noun} {verb} por expiração.")

    if st.session_state.active_conversation_id and not any(
        str(row["id"]) == str(st.session_state.active_conversation_id)
        for row in sessions
    ):
        had_pending_action = st.session_state.pending_action is not None
        st.session_state.active_conversation_id = None
        st.session_state.messages = []
        st.session_state.pending_action = None
        st.session_state.pending_review = None
        st.session_state.storage_notice = (
            "A conversa ativa não está mais disponível no histórico."
        )
        if had_pending_action:
            st.session_state.storage_notice += " A ação pendente foi cancelada."

    for group, group_rows in grouped_sessions(sessions).items():
        if not group_rows:
            continue
        with st.sidebar.expander(group, expanded=group == "Hoje"):
            for row in group_rows:
                session_id = str(row["id"])
                label = (row.get("title") or "Nova conversa").strip()[:48]
                session_col, favorite_col, delete_col = st.columns([6, 1, 1])
                with session_col:
                    if st.button(
                        label,
                        key=f"open_session_{session_id}",
                        type=(
                            "primary"
                            if session_id == st.session_state.active_conversation_id
                            else "tertiary"
                        ),
                        use_container_width=True,
                    ):
                        open_conversation(session_id, sessions)
                with favorite_col:
                    favorite_label = "★" if row.get("is_favorite") else "☆"
                    if st.button(
                        favorite_label,
                        key=f"favorite_session_{session_id}",
                        help=(
                            "Remover dos favoritos"
                            if row.get("is_favorite")
                            else "Favoritar conversa"
                        ),
                        type="tertiary",
                    ):
                        try:
                            conversation_repository.set_favorite(
                                current_user_id,
                                session_id,
                                not bool(row.get("is_favorite")),
                            )
                            st.rerun()
                        except Exception as error:
                            logger.exception("Não foi possível atualizar favorito.")
                            st.sidebar.error(f"Não foi possível favoritar: {error}")
                with delete_col:
                    if st.button(
                        "Excluir",
                        key=f"delete_session_{session_id}",
                        help="Excluir conversa",
                        type="tertiary",
                    ):
                        st.session_state.delete_confirmation_id = session_id

    confirm_id = st.session_state.delete_confirmation_id
    if confirm_id:
        with st.sidebar.container(border=True):
            st.warning("Excluir esta conversa e as consultas ligadas a ela?")
            if st.button(
                "Confirmar exclusão",
                key="confirm_delete_session",
                type="primary",
            ):
                try:
                    conversation_repository.delete(current_user_id, confirm_id)
                    if str(st.session_state.active_conversation_id) == str(confirm_id):
                        st.session_state.active_conversation_id = None
                        st.session_state.messages = []
                        st.session_state.pending_review = None
                    st.session_state.delete_confirmation_id = None
                    st.rerun()
                except Exception as error:
                    logger.exception("Não foi possível excluir a conversa.")
                    st.sidebar.error(f"Não foi possível excluir: {error}")
            if st.button("Cancelar", key="cancel_delete_session"):
                st.session_state.delete_confirmation_id = None
                st.rerun()
    return sessions


def render_query_history():
    with st.sidebar.expander("Histórico de consultas"):
        if query_history is None:
            st.caption("Histórico indisponível.")
            return
        try:
            history_rows = query_history.list(current_user_id)
        except Exception as error:
            logger.exception("Não foi possível carregar o histórico de consultas.")
            st.error(f"Não foi possível carregar o histórico: {error}")
            return
        if not history_rows:
            st.caption("Nenhuma consulta executada ainda.")
            return

        with st.container(height=300, border=True):
            for row in history_rows:
                history_id = row["id"]
                prompt_label = (row.get("prompt") or "Consulta compartilhada").strip()
                prompt_col, execute_col, pin_col, delete_col = st.columns([5, 1, 1, 1])
                with prompt_col:
                    st.markdown(f"**{prompt_label[:48]}**")
                with execute_col:
                    if st.button(
                        "▶",
                        key=f"run_history_{history_id}",
                        help=f"Executar consulta: {row['sql'][:180]}",
                        type="tertiary",
                        disabled=st.session_state.pending_action is not None,
                    ):
                        if add_query_action(
                            prompt_label,
                            row["sql"],
                            row.get("source", "chat"),
                            row.get("parameters") or {},
                        ):
                            st.rerun()
                with pin_col:
                    pin_label = "📌" if row.get("is_pinned") else "📍"
                    if st.button(
                        pin_label,
                        key=f"pin_history_{history_id}",
                        help=(
                            "Desafixar"
                            if row.get("is_pinned")
                            else "Fixar no topo"
                        ),
                        type="tertiary",
                    ):
                        try:
                            query_history.set_pinned(
                                current_user_id,
                                history_id,
                                not row.get("is_pinned", False),
                            )
                            st.rerun()
                        except Exception as error:
                            logger.exception("Não foi possível fixar a consulta.")
                            st.error(f"Não foi possível atualizar: {error}")
                with delete_col:
                    if st.button(
                        "🗑",
                        key=f"delete_history_{history_id}",
                        help="Excluir consulta",
                        type="tertiary",
                    ):
                        try:
                            query_history.delete(current_user_id, history_id)
                            st.rerun()
                        except Exception as error:
                            logger.exception("Não foi possível excluir a consulta.")
                            st.error(f"Não foi possível excluir: {error}")


def render_predefined_queries():
    with st.sidebar.expander("Consultas compartilhadas"):
        if not catalog_available:
            st.warning(
                "Catálogo indisponível. Verifique a conexão com o PostgreSQL e recarregue a página."
            )
            return
        try:
            query_rows = get_predefined_query_rows(
                predefined_queries, current_user_id
            )
        except Exception as error:
            logger.exception("Não foi possível carregar o catálogo.")
            st.error(f"Não foi possível carregar o catálogo: {error}")
            return

        selected = None
        selected_id = None
        if query_rows:
            labels = {row["id"]: row["name"] for row in query_rows}
            selected_id = st.selectbox(
                "Escolha uma consulta",
                list(labels),
                format_func=labels.get,
            )
            selected = next(row for row in query_rows if row["id"] == selected_id)
            st.caption(selected["description"] or "Sem descrição")
            st.caption(
                f"Autor: {selected['author']} | Tags: {', '.join(selected['tags'] or [])}"
            )

            favorite = st.checkbox(
                "Favorita",
                value=bool(selected["is_favorite"]),
                key=f"favorite_{selected_id}",
            )
            if favorite != bool(selected["is_favorite"]):
                try:
                    predefined_queries.toggle_favorite(
                        current_user_id, selected_id, favorite
                    )
                    get_predefined_query_rows.clear()
                    st.rerun()
                except Exception as error:
                    logger.exception("Não foi possível atualizar a consulta favorita.")
                    st.error(f"Não foi possível atualizar: {error}")

            parameters = selected["parameters"] or []
            values = {
                parameter["name"]: st.text_input(
                    parameter.get("label", parameter["name"]),
                    key=f"param_{selected_id}_{parameter['name']}",
                )
                for parameter in parameters
            }
            if st.button(
                "Executar consulta",
                type="primary",
                use_container_width=True,
                disabled=st.session_state.pending_action is not None,
            ):
                if add_query_action(
                    selected["name"], selected["sql"], "predefined", values
                ):
                    st.rerun()
        else:
            st.caption("Nenhuma consulta cadastrada.")

        if current_role in {"dev", "developer", "dba", "admin"}:
            with st.expander("Administrar catálogo"):
                with st.form("new_predefined_query"):
                    name = st.text_input("Nome")
                    description = st.text_input("Descrição")
                    sql = st.text_area("SQL", height=120)
                    tags = st.text_input("Tags (separadas por vírgula)")
                    parameters_json = st.text_area("Parâmetros JSON", value="[]")
                    if st.form_submit_button("Criar consulta"):
                        try:
                            predefined_queries.create(
                                name,
                                description,
                                sql,
                                [
                                    tag.strip()
                                    for tag in tags.split(",")
                                    if tag.strip()
                                ],
                                current_user_email,
                                json.loads(parameters_json),
                            )
                            get_predefined_query_rows.clear()
                            st.success("Consulta criada.")
                            st.rerun()
                        except Exception as error:
                            logger.exception("Não foi possível criar a consulta.")
                            st.error(f"Não foi possível criar: {error}")
                if selected:
                    with st.form("edit_predefined_query"):
                        edit_name = st.text_input("Nome", value=selected["name"])
                        edit_description = st.text_input(
                            "Descrição", value=selected["description"]
                        )
                        edit_sql = st.text_area(
                            "SQL", value=selected["sql"], height=120
                        )
                        edit_tags = st.text_input(
                            "Tags (separadas por vírgula)",
                            value=", ".join(selected["tags"] or []),
                        )
                        edit_parameters = st.text_area(
                            "Parâmetros JSON",
                            value=json.dumps(
                                selected["parameters"] or [], ensure_ascii=True
                            ),
                        )
                        if st.form_submit_button("Salvar alterações"):
                            try:
                                predefined_queries.update(
                                    selected_id,
                                    edit_name,
                                    edit_description,
                                    edit_sql,
                                    [
                                        tag.strip()
                                        for tag in edit_tags.split(",")
                                        if tag.strip()
                                    ],
                                    json.loads(edit_parameters),
                                )
                                get_predefined_query_rows.clear()
                                st.success("Consulta atualizada.")
                                st.rerun()
                            except Exception as error:
                                logger.exception("Não foi possível atualizar a consulta.")
                                st.error(f"Não foi possível atualizar: {error}")
                    if st.button(
                        "Excluir consulta selecionada", key="delete_predefined"
                    ):
                        try:
                            predefined_queries.delete(selected_id)
                            get_predefined_query_rows.clear()
                            st.success("Consulta excluída.")
                            st.rerun()
                        except Exception as error:
                            logger.exception("Não foi possível excluir a consulta.")
                            st.error(f"Não foi possível excluir: {error}")


def render_user_administration():
    if current_role != "admin":
        return

    with st.sidebar.expander("Administrar usuários"):
        try:
            profiles = user_repository.list_profiles()
        except Exception as error:
            logger.exception("Não foi possível carregar usuários.")
            st.error(f"Não foi possível carregar usuários: {error}")
            return
        if not profiles:
            st.caption("Nenhum usuário cadastrado.")
            return

        profile_labels = {
            str(item["id"]): f"{item['email']} ({item['status']})"
            for item in profiles
        }
        target_id = st.selectbox(
            "Usuário",
            list(profile_labels),
            format_func=profile_labels.get,
            key="admin_target_user",
        )
        target = next(item for item in profiles if str(item["id"]) == target_id)
        st.caption(target["name"] or "Nome não informado")

        with st.form("admin_user_changes"):
            new_status = st.selectbox(
                "Status",
                ["pending", "approved", "rejected", "disabled"],
                index=["pending", "approved", "rejected", "disabled"].index(
                    target["status"]
                ),
            )
            new_role = st.selectbox(
                "Papel",
                ["user", "dev", "admin"],
                index=["user", "dev", "admin"].index(target["role"]),
            )
            if st.form_submit_button("Salvar usuário"):
                try:
                    user_repository.set_status(
                        target_id, new_status, current_user_id
                    )
                    user_repository.set_role(target_id, new_role, current_user_id)
                    st.success("Usuário atualizado.")
                    st.rerun()
                except Exception as error:
                    logger.exception("Não foi possível atualizar usuário.")
                    st.error(f"Não foi possível atualizar: {error}")


def is_read_only_sql(sql):
    try:
        PredefinedQueryRepository.validate_query(sql, [])
    except (AttributeError, TypeError, ValueError):
        return False
    return True


def queue_retry(message):
    if st.session_state.pending_action is not None:
        return
    request_id = str(message["request_id"])
    user_message = next(
        (
            item
            for item in st.session_state.messages
            if item["role"] == "user"
            and str(item.get("request_id")) == request_id
        ),
        None,
    )
    if user_message is None:
        st.session_state.storage_notice = (
            "Não foi possível identificar a pergunta original para tentar novamente."
        )
        return
    turn = {
        "session_id": st.session_state.active_conversation_id,
        "request_id": request_id,
        "prompt": user_message["content"],
    }
    if message.get("retry_kind") == "translate":
        action = {"kind": "translate", "turn": turn, "retry": True}
    else:
        if not is_read_only_sql(message.get("sql", "")):
            return
        action = {
            "kind": "execute",
            "turn": turn,
            "sql": message["sql"],
            "source": message.get("source", "chat"),
            "parameters": message.get("parameters") or {},
            "grafico": message.get("grafico"),
            "retry": True,
        }
    message["retryable"] = False
    st.session_state.pending_action = action
    st.rerun()


def process_translation(action, review_mode):
    turn = action["turn"]
    try:
        context = conversation_repository.get_context(
            current_user_id,
            turn["session_id"],
            limit=6,
            exclude_request_id=turn["request_id"] if action.get("retry") else None,
        )
        with st.chat_message("assistant"):
            with st.spinner("Traduzindo sua pergunta para SQL..."):
                response_data = translator.translate_to_sql(
                    turn["prompt"], conversation_context=context
                )
        sql = (response_data.get("sql") or "").strip()
        grafico = response_data.get("grafico")
        if sql.startswith("AVISO:"):
            save_assistant_turn(turn, sql)
            return
        if not sql:
            raise ValueError("A tradução não retornou uma consulta SQL.")
    except Exception as error:
        logger.exception("Erro na tradução da pergunta.")
        save_assistant_turn(
            turn,
            "Não foi possível traduzir a pergunta.",
            error=str(error),
            metadata={
                "retryable": True,
                "retry_kind": "translate",
            },
        )
        return

    if review_mode:
        save_assistant_turn(
            turn,
            "SQL gerado para revisão.",
            sql=sql,
            metadata={"grafico": grafico},
        )
        st.session_state.pending_review = {
            "turn": turn,
            "sql": sql,
            "grafico": grafico,
            "source": "chat",
            "parameters": {},
        }
        return

    save_assistant_turn(
        turn,
        "SQL gerado; consulta em execução.",
        sql=sql,
        metadata={"grafico": grafico},
    )
    st.session_state.pending_action = {
        "kind": "execute",
        "turn": turn,
        "sql": sql,
        "source": "chat",
        "parameters": {},
        "grafico": grafico,
        "retry": False,
    }


def process_query(action):
    turn = action["turn"]
    sql = action["sql"]
    parameters = action.get("parameters") or {}
    source = action.get("source", "chat")
    grafico = action.get("grafico")
    if not any(
        message["role"] == "assistant"
        and str(message.get("request_id")) == str(turn["request_id"])
        for message in st.session_state.messages
    ):
        save_assistant_turn(
            turn,
            "Consulta em execução.",
            sql=sql,
            metadata={"grafico": grafico},
        )

    try:
        with st.chat_message("assistant"):
            with st.spinner("Executando consulta no banco..."):
                if action.get("retry"):
                    df = get_db_adapter().execute_read_only_query(sql, parameters)
                else:
                    df = get_db_adapter().execute_query(sql, parameters)
    except Exception as error:
        logger.exception("Erro na execução da query.")
        retryable = is_read_only_sql(sql)
        save_assistant_turn(
            turn,
            "Houve um problema ao executar a consulta.",
            sql=sql,
            error=str(error),
            metadata={
                "retryable": retryable,
                "retry_kind": "execute" if retryable else None,
                "parameters": parameters,
                "source": source,
                "grafico": grafico,
            },
        )
        return

    result_content = "Aqui estão os resultados da consulta:"
    if query_history is not None:
        try:
            query_history.record(
                current_user_id,
                turn["prompt"],
                sql,
                source,
                parameters,
                session_id=turn["session_id"],
            )
        except Exception as error:
            logger.exception("Não foi possível salvar a consulta no histórico.")
            result_content += (
                f"\n\nAviso: a consulta foi executada, mas não foi salva no histórico. ({error})"
            )
    save_assistant_turn(
        turn,
        result_content,
        sql=sql,
        metadata={"grafico": grafico},
        df=df,
    )


st.title("Ask SQL")
st.subheader("Converse com seus dados")
st.caption("Faça perguntas em linguagem natural e acompanhe cada consulta em uma conversa.")
st.sidebar.caption(f"{current_user_email} | {current_role}")
if st.sidebar.button("Sair", key="logout"):
    try:
        auth_service.sign_out()
        st.session_state.auth_user = None
        clear_chat_state()
        st.rerun()
    except Exception as error:
        logger.exception("Não foi possível encerrar a sessão.")
        st.sidebar.error(f"Não foi possível sair: {error}")

review_mode = st.sidebar.toggle(
    "Revisar SQL antes de executar", value=True, key="review_sql"
)
if st.sidebar.button("🔄 Sincronizar Banco", use_container_width=True):
    get_translator.clear()
    get_predefined_query_repository.clear()
    get_predefined_query_rows.clear()
    st.toast("Esquema do banco de dados atualizado.")
st.sidebar.caption("Suas conversas são privadas e os resultados são atualizados ao executar o SQL.")

render_conversation_sidebar()
render_predefined_queries()
render_query_history()
render_user_administration()

render_chat_messages(
    st.session_state.messages,
    on_retry=queue_retry,
    action_pending=st.session_state.pending_action is not None,
)
if st.session_state.storage_notice:
    st.error(st.session_state.storage_notice)

pending_review = st.session_state.pending_review
if pending_review:
    with st.container(border=True):
        st.markdown("#### SQL aguardando revisão")
        st.caption("O SQL está exibido na mensagem acima.")
        run_col, cancel_col = st.columns([1, 1])
        with run_col:
            if st.button("Executar SQL revisado", type="primary"):
                st.session_state.pending_action = {
                    "kind": "execute",
                    **pending_review,
                    "retry": False,
                }
                st.session_state.pending_review = None
                st.rerun()
        with cancel_col:
            if st.button("Cancelar revisão", key="cancel_sql_review"):
                st.session_state.pending_review = None
                st.rerun()

pending_action = st.session_state.pending_action
if pending_action:
    st.session_state.pending_action = None
    if pending_action["kind"] == "translate":
        process_translation(pending_action, review_mode)
    elif pending_action["kind"] == "execute":
        process_query(pending_action)
    st.rerun()

prompt = st.chat_input(
    "Faça sua pergunta sobre os dados...",
    disabled=(
        conversation_repository is None
        or st.session_state.pending_action is not None
    ),
)
if prompt:
    st.session_state.pending_review = None
    turn = persist_user_turn(prompt)
    if turn:
        st.session_state.pending_action = {
            "kind": "translate",
            "turn": turn,
            "retry": False,
        }
    st.rerun()
