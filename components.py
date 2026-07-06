import streamlit as st
import pandas as pd
import logging
from database.base import DatabaseAdapter

logger = logging.getLogger(__name__)

def render_chat_message(i: int, msg: dict):
    """Renderiza uma única mensagem do histórico do chat no Streamlit."""
    with st.chat_message(msg["role"]):
        if msg["content"].startswith("AVISO:"):
            st.warning(msg["content"])
        else:
            st.write(msg["content"])
            
        if "sql" in msg and msg["sql"]:
            st.code(msg["sql"], language="sql")
        
        if "error" in msg and msg["error"]:
            st.error(msg["error"])

        if "df" in msg and msg["df"] is not None:
            df: pd.DataFrame = msg["df"]
            st.dataframe(df)
            
            # Lógica do Gráfico "Stand By"
            if "grafico" in msg and msg["grafico"] and msg["grafico"].get("tipo"):
                if not msg.get("show_chart", False):
                    # Botão para renderizar sob demanda
                    if st.button("📊 Gerar Gráfico", key=f"btn_chart_{i}"):
                        msg["show_chart"] = True
                        st.rerun()
                
                if msg.get("show_chart", False):
                    cfg = msg["grafico"]
                    tipo = cfg.get("tipo")
                    x = cfg.get("eixo_x")
                    y = cfg.get("eixo_y")
                    
                    st.markdown(f"**{cfg.get('titulo', 'Visualização de Dados')}**")
                    try:
                        if x in df.columns and y in df.columns:
                            if tipo == "bar":
                                st.bar_chart(df, x=x, y=y)
                            elif tipo == "line":
                                st.line_chart(df, x=x, y=y)
                            else:
                                st.warning(f"Tipo de gráfico '{tipo}' não suportado pelo sistema.")
                        else:
                            st.warning("As colunas sugeridas pela IA para o gráfico não existem no DataFrame retornado.")
                    except Exception as e:
                        logger.error(f"Erro ao desenhar o gráfico: {e}")
                        st.error(f"Erro ao desenhar o gráfico: {e}")

            # Download do CSV
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Relatório (CSV)",
                data=csv,
                file_name=f"relatorio_{i}.csv",
                mime="text/csv",
                key=f"download_{i}"
            )

def render_pending_sql(db_adapter: DatabaseAdapter):
    """Renderiza e gerencia a execução de queries em estado de revisão."""
    if st.session_state.pending_sql:
        with st.chat_message("assistant"):
            st.write("SQL gerado (Aguardando revisão):")
            st.code(st.session_state.pending_sql, language="sql")
            
            if st.button("Executar Query", type="primary"):
                sql_to_run = st.session_state.pending_sql
                grafico_to_run = st.session_state.pending_grafico

                st.session_state.pending_sql = None
                st.session_state.pending_grafico = None
                
                with st.spinner("Executando consulta no banco..."):
                    try:
                        df = db_adapter.execute_query(sql_to_run)
                        st.session_state.messages.append({"role": "assistant", "content": "Aqui estão os resultados da consulta:", "sql": sql_to_run, "df": df, "grafico": grafico_to_run, "show_chart": False})
                        st.rerun()
                    except Exception as db_err:
                        logger.error(f"Erro na execução da query: {db_err}")
                        st.error(f"Erro na execução da query: {db_err}")
                        st.session_state.messages.append({"role": "assistant", "content": "Houve um problema ao executar a consulta.", "sql": sql_to_run, "error": str(db_err)})