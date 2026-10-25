import streamlit as st
import pandas as pd
import logging
import json
from core.prompter import Prompter
from core.translator import Translator
from core.auth import AuthConfigurationError, SupabaseAuth
from database.postgres import PostgresAdapter
from database.predefined_queries import PredefinedQueryRepository
from database.query_history import QueryHistoryRepository
from database.users import UserRepository
from components import render_chat_message, render_pending_sql # Configuração global de logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Configuração da página
st.set_page_config(page_title="Ask SQL", layout="wide")

# Instanciação dos serviços
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

@st.cache_resource(ttl=60)
def get_translator():
    """Cache do tradutor e do prompt de sistema."""
    prompter = Prompter()
    db = get_db_adapter()
    live_schema = db.get_schema_info()
    system_prompt = prompter.build_system_prompt(live_schema=live_schema)
    # Utilizando o modelo especificado localmente
    return Translator(system_prompt=system_prompt, model_name="qwen2.5-coder:7b")


@st.cache_resource
def get_predefined_query_repository():
    repository = PredefinedQueryRepository(get_db_adapter())
    repository.initialize()
    return repository


@st.cache_resource
def get_query_history_repository(cache_version=3):
    repository = QueryHistoryRepository(get_db_adapter())
    repository.initialize()
    return repository


@st.cache_data(ttl=15)
def get_predefined_query_rows(_repository, user_name):
    return _repository.list(user_name)


db_adapter = get_db_adapter()
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


if "auth_user" not in st.session_state:
    st.session_state.auth_user = None


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
                    user, _session = auth_service.sign_in(email.strip(), password)
                    st.session_state.auth_user = {
                        "id": str(user.id), "email": user.email or email.strip()
                    }
                    st.rerun()
                except Exception as error:
                    st.error(f"Não foi possível entrar: {error}")

    with signup_tab:
        with st.form("signup_form"):
            name = st.text_input("Nome completo")
            email = st.text_input("Email", key="signup_email")
            password = st.text_input("Senha", type="password", key="signup_password")
            password_confirmation = st.text_input("Confirmar senha", type="password")
            if st.form_submit_button("Solicitar acesso"):
                if not name.strip() or not email.strip():
                    st.error("Informe nome e email.")
                elif len(password) < 8:
                    st.error("A senha deve ter pelo menos 8 caracteres.")
                elif password != password_confirmation:
                    st.error("As senhas não conferem.")
                else:
                    try:
                        user, normalized_name = auth_service.sign_up(email.strip(), password, name)
                        user_repository.create_pending_profile(
                            user.id, user.email or email.strip(), normalized_name
                        )
                        st.success("Cadastro recebido. Confirme seu email e aguarde a aprovação de um admin.")
                    except Exception as error:
                        st.error(f"Não foi possível criar a conta: {error}")


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
        st.rerun()
    st.stop()

translator = get_translator()
predefined_queries = None
query_history = None
catalog_available = True
try:
    predefined_queries = get_predefined_query_repository()
except Exception as error:
    catalog_available = False
    logger.warning("Catálogo de consultas indisponível: %s", error)
try:
    query_history = get_query_history_repository(3)
except Exception as error:
    logger.warning("Histórico de consultas indisponível: %s", error)
current_user_id = auth_user["id"]
current_user_email = profile["email"]
current_role = profile["role"]

# Cabeçalho e Toggle
st.title("Ask SQL - Converse com seus dados")
st.sidebar.caption(f"{current_user_email} | {current_role}")
if st.sidebar.button("Sair", key="logout"):
    auth_service.sign_out()
    st.session_state.auth_user = None
    st.session_state.messages = []
    st.rerun()
review_mode = st.sidebar.toggle("Revisar SQL antes de executar", value=True)
st.sidebar.markdown("---")

if st.sidebar.button("🔄 Sincronizar Banco", use_container_width=True):
    get_translator.clear()
    get_predefined_query_repository.clear()
    get_predefined_query_rows.clear()
    st.toast("Esquema do banco de dados atualizado com sucesso!")

st.sidebar.info("Este aplicativo traduz sua pergunta para SQL, consulta o PostgreSQL e retorna os dados.")


def render_query_history():
    st.sidebar.markdown("### Histórico recente")
    if query_history is None:
        st.sidebar.caption("Histórico indisponível.")
        return
    try:
        history_rows = query_history.list(current_user_id)
    except Exception as error:
        st.sidebar.error(f"Não foi possível carregar o histórico: {error}")
        return
    if not history_rows:
        st.sidebar.caption("Nenhuma consulta executada ainda.")
        return

    with st.sidebar.container(height=300, border=True):
        for row in history_rows:
            history_id = row["id"]
            prompt_label = (row["prompt"] or "Consulta compartilhada").strip()
            prompt_col, execute_col, pin_col, delete_col = st.columns([5, 1, 1, 1])
            with prompt_col:
                st.markdown(f"**{prompt_label[:48]}**")
            with execute_col:
                if st.button(
                    "▶", key=f"run_history_{history_id}",
                    help=f"Executar consulta: {row['sql'][:180]}", type="tertiary",
                ):
                    try:
                        with st.spinner("Executando consulta..."):
                            df = db_adapter.execute_query(row["sql"], row.get("parameters") or {})
                        query_history.record(
                            current_user_id, row["prompt"], row["sql"], row["source"],
                            row.get("parameters") or {},
                        )
                        st.session_state.messages.append({
                            "role": "assistant", "content": "Resultado da consulta anterior:",
                            "sql": row["sql"], "df": df, "grafico": None, "show_chart": False,
                        })
                        st.rerun()
                    except Exception as error:
                        st.error(f"Erro na execução: {error}")
            with pin_col:
                pin_label = "📌" if row.get("is_pinned") else "📍"
                if st.button(
                    pin_label, key=f"pin_history_{history_id}",
                    help="Fixar no topo" if not row.get("is_pinned") else "Desafixar",
                    type="tertiary",
                ):
                    query_history.set_pinned(current_user_id, history_id, not row.get("is_pinned", False))
                    st.rerun()
            with delete_col:
                if st.button(
                    "🗑", key=f"delete_history_{history_id}", help="Excluir consulta",
                    type="tertiary",
                ):
                    query_history.delete(current_user_id, history_id)
                    st.rerun()


def render_predefined_queries():
    st.sidebar.markdown("### Consultas compartilhadas")
    st.sidebar.caption(f"Usuário: {current_user_email} | Papel: {current_role}")
    if not catalog_available:
        st.sidebar.warning("Catálogo indisponível. Verifique a conexão com o PostgreSQL e recarregue a página.")
        return

    try:
        query_rows = get_predefined_query_rows(predefined_queries, current_user_id)
    except Exception as error:
        st.sidebar.error(f"Não foi possível carregar o catálogo: {error}")
        return

    selected = None
    selected_id = None
    if query_rows:
        labels = {row["id"]: row["name"] for row in query_rows}
        selected_id = st.sidebar.selectbox("Escolha uma consulta", list(labels), format_func=labels.get)
        selected = next(row for row in query_rows if row["id"] == selected_id)
        st.sidebar.caption(selected["description"] or "Sem descrição")
        st.sidebar.caption(f"Autor: {selected['author']} | Tags: {', '.join(selected['tags'] or [])}")

        favorite = st.sidebar.checkbox("Favorita", value=bool(selected["is_favorite"]), key=f"favorite_{selected_id}")
        if favorite != bool(selected["is_favorite"]):
            predefined_queries.toggle_favorite(current_user_id, selected_id, favorite)
            get_predefined_query_rows.clear()
            st.rerun()

        parameters = selected["parameters"] or []
        values = {parameter["name"]: st.sidebar.text_input(
            parameter.get("label", parameter["name"]), key=f"param_{selected_id}_{parameter['name']}"
        ) for parameter in parameters}
        if st.sidebar.button("Executar consulta", type="primary", use_container_width=True):
            try:
                with st.spinner("Executando consulta..."):
                    df = db_adapter.execute_query(selected["sql"], values)
                if query_history:
                    query_history.record(
                        current_user_id, selected["name"], selected["sql"], "predefined", values
                    )
                st.session_state.messages.append({
                    "role": "assistant", "content": f"Resultado de: {selected['name']}",
                    "sql": selected["sql"], "df": df, "grafico": None, "show_chart": False,
                })
                st.rerun()
            except Exception as error:
                st.sidebar.error(f"Erro na execução: {error}")
    else:
        st.sidebar.caption("Nenhuma consulta cadastrada.")

    if current_role in {"developer", "dba", "admin"}:
        with st.sidebar.expander("Administrar catálogo"):
            with st.form("new_predefined_query"):
                name = st.text_input("Nome")
                description = st.text_input("Descrição")
                sql = st.text_area("SQL", height=120)
                tags = st.text_input("Tags (separadas por vírgula)")
                parameters_json = st.text_area("Parâmetros JSON", value="[]")
                if st.form_submit_button("Criar consulta"):
                    try:
                        predefined_queries.create(name, description, sql, [tag.strip() for tag in tags.split(",") if tag.strip()], current_user_email, json.loads(parameters_json))
                        get_predefined_query_rows.clear()
                        st.success("Consulta criada.")
                        st.rerun()
                    except Exception as error:
                        st.error(f"Não foi possível criar: {error}")
            if selected:
                with st.form("edit_predefined_query"):
                    edit_name = st.text_input("Nome", value=selected["name"])
                    edit_description = st.text_input("Descrição", value=selected["description"])
                    edit_sql = st.text_area("SQL", value=selected["sql"], height=120)
                    edit_tags = st.text_input("Tags (separadas por vírgula)", value=", ".join(selected["tags"] or []))
                    edit_parameters = st.text_area("Parâmetros JSON", value=json.dumps(selected["parameters"] or [], ensure_ascii=True))
                    if st.form_submit_button("Salvar alterações"):
                        try:
                            predefined_queries.update(selected_id, edit_name, edit_description, edit_sql, [tag.strip() for tag in edit_tags.split(",") if tag.strip()], json.loads(edit_parameters))
                            get_predefined_query_rows.clear()
                            st.success("Consulta atualizada.")
                            st.rerun()
                        except Exception as error:
                            st.error(f"Não foi possível atualizar: {error}")
                if st.button("Excluir consulta selecionada", key="delete_predefined"):
                    predefined_queries.delete(selected_id)
                    get_predefined_query_rows.clear()
                    st.success("Consulta excluída.")
                    st.rerun()


def render_user_administration():
    if current_role != "admin":
        return

    with st.sidebar.expander("Administrar usuários"):
        try:
            profiles = user_repository.list_profiles()
        except Exception as error:
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
            "Usuário", list(profile_labels), format_func=profile_labels.get,
            key="admin_target_user"
        )
        target = next(item for item in profiles if str(item["id"]) == target_id)
        st.caption(target["name"] or "Nome não informado")

        with st.form("admin_user_changes"):
            new_status = st.selectbox(
                "Status", ["pending", "approved", "rejected", "disabled"],
                index=["pending", "approved", "rejected", "disabled"].index(target["status"]),
            )
            new_role = st.selectbox(
                "Papel", ["user", "dev", "admin"],
                index=["user", "dev", "admin"].index(target["role"]),
            )
            if st.form_submit_button("Salvar usuário"):
                try:
                    user_repository.set_status(target_id, new_status, current_user_id)
                    user_repository.set_role(target_id, new_role, current_user_id)
                    st.success("Usuário atualizado.")
                    st.rerun()
                except Exception as error:
                    st.error(f"Não foi possível atualizar: {error}")


render_predefined_queries()
render_query_history()
render_user_administration()

# Inicialização do estado
if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending_sql" not in st.session_state:
    st.session_state.pending_sql = None

if "pending_grafico" not in st.session_state:
    st.session_state.pending_grafico = None

if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None

# Renderizar histórico de mensagens
for i, msg in enumerate(st.session_state.messages):
    render_chat_message(i, msg)

# Input do usuário
if prompt := st.chat_input("Faça sua pergunta sobre os dados..."):
    # Nova pergunta cancela qualquer SQL pendente
    st.session_state.pending_sql = None
    st.session_state.pending_grafico = None
    st.session_state.pending_prompt = None
    
    # Adicionar pergunta ao histórico
    st.session_state.messages.append({
        "role": "user", 
        "content": prompt
    })
    
    with st.chat_message("user"):
        st.write(prompt)
        
    with st.chat_message("assistant"):
        with st.spinner("Traduzindo para SQL..."):
            try:
                response_data = translator.translate_to_sql(prompt)
                sql = response_data.get("sql", "")
                grafico = response_data.get("grafico", None)
                
                if sql.startswith("AVISO:"):
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": sql
                    })
                    st.rerun()
                elif review_mode:
                    # Deixa para revisão
                    st.session_state.pending_sql = sql
                    st.session_state.pending_grafico = grafico
                    st.session_state.pending_prompt = prompt
                    st.rerun()
                else:
                    # Executa imediatamente
                    st.write("SQL Gerado e Executado:")
                    st.code(sql, language="sql")
                    
                    try:
                        with st.spinner("Executando consulta no banco..."):
                            df = db_adapter.execute_query(sql)
                        if query_history:
                            query_history.record(current_user_id, prompt, sql)
                            
                        # Salva histórico
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": "Aqui estão os resultados da consulta:",
                            "sql": sql,
                            "df": df,
                            "grafico": grafico,
                            "show_chart": False
                        })
                        st.rerun()
                    except Exception as db_err:
                        # Erro de SQL (Fase 5)
                        logger.error(f"Erro na execução da query: {db_err}")
                        st.error(f"Erro na execução da query: {db_err}")
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": "Houve um problema ao executar a consulta. Por favor, reescreva sua pergunta ou verifique a sintaxe.",
                            "sql": sql,
                            "error": str(db_err)
                        })

            except Exception as e:
                logger.error(f"Erro na tradução: {e}")
                st.error(f"Erro na tradução: {e}")

# Se há um SQL pendente aguardando revisão
render_pending_sql(db_adapter, query_history, current_user_id)
