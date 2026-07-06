import streamlit as st
import pandas as pd
import logging
from core.prompter import Prompter
from core.translator import Translator
from database.postgres import PostgresAdapter
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

@st.cache_resource(ttl=60)
def get_translator():
    """Cache do tradutor e do prompt de sistema."""
    prompter = Prompter()
    db = get_db_adapter()
    live_schema = db.get_schema_info()
    system_prompt = prompter.build_system_prompt(live_schema=live_schema)
    # Utilizando o modelo especificado localmente
    return Translator(system_prompt=system_prompt, model_name="qwen2.5-coder:7b")

db_adapter = get_db_adapter()
translator = get_translator()

# Cabeçalho e Toggle
st.title("Ask SQL - Converse com seus dados")
review_mode = st.sidebar.toggle("Revisar SQL antes de executar", value=True)
st.sidebar.markdown("---")

if st.sidebar.button("🔄 Sincronizar Banco", use_container_width=True):
    get_translator.clear()
    st.toast("Esquema do banco de dados atualizado com sucesso!")

st.sidebar.info("Este aplicativo traduz sua pergunta para SQL, consulta o PostgreSQL e retorna os dados.")

# Inicialização do estado
if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending_sql" not in st.session_state:
    st.session_state.pending_sql = None

if "pending_grafico" not in st.session_state:
    st.session_state.pending_grafico = None

# Renderizar histórico de mensagens
for i, msg in enumerate(st.session_state.messages):
    render_chat_message(i, msg)

# Input do usuário
if prompt := st.chat_input("Faça sua pergunta sobre os dados..."):
    # Nova pergunta cancela qualquer SQL pendente
    st.session_state.pending_sql = None
    st.session_state.pending_grafico = None
    
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
                    st.rerun()
                else:
                    # Executa imediatamente
                    st.write("SQL Gerado e Executado:")
                    st.code(sql, language="sql")
                    
                    try:
                        with st.spinner("Executando consulta no banco..."):
                            df = db_adapter.execute_query(sql)
                            
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
render_pending_sql(db_adapter)
