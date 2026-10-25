from unittest.mock import MagicMock
from types import SimpleNamespace

import pandas as pd
import pytest

import components


@pytest.fixture
def streamlit(monkeypatch):
    fake = MagicMock()
    fake.session_state = SimpleNamespace(
        pending_sql=None,
        pending_grafico=None,
        pending_prompt=None,
        messages=[],
    )
    fake.button.return_value = False
    monkeypatch.setattr(components, "st", fake)
    return fake


def test_render_chat_messages_renders_each_transcript_message_once(streamlit):
    messages = [
        {"role": "user", "content": "Quantos clientes?"},
        {"role": "assistant", "content": "Encontrei 12 clientes."},
    ]

    components.render_chat_messages(messages)

    assert [call.args[0] for call in streamlit.chat_message.call_args_list] == [
        "user",
        "assistant",
    ]
    assert [call.args[0] for call in streamlit.write.call_args_list] == [
        messages[0]["content"],
        messages[1]["content"],
    ]


def test_render_chat_messages_is_stable_across_full_rerenders(streamlit):
    messages = [{"role": "user", "content": "Quantos clientes?"}]

    components.render_chat_messages(messages)
    streamlit.chat_message.reset_mock()
    streamlit.rerun.reset_mock()
    components.render_chat_messages(messages)

    assert streamlit.chat_message.call_count == 1
    assert streamlit.chat_message.call_args.args == ("user",)
    streamlit.rerun.assert_not_called()


def test_retryable_message_invokes_the_retry_action_once(streamlit):
    streamlit.button.return_value = True
    on_retry = MagicMock()
    message = {
        "role": "assistant",
        "content": "A consulta falhou.",
        "request_id": "turn-1",
        "retryable": True,
        "retry_kind": "translate",
    }

    components.render_chat_message(0, message, on_retry=on_retry)

    on_retry.assert_called_once_with(message)
    assert streamlit.button.call_args.kwargs["key"] == "retry_turn-1"


def test_retry_button_is_disabled_while_an_action_is_active(streamlit):
    on_retry = MagicMock()
    message = {
        "role": "assistant",
        "content": "A consulta falhou.",
        "request_id": "turn-1",
        "retryable": True,
    }

    components.render_chat_message(
        0, message, on_retry=on_retry, action_pending=True
    )

    assert streamlit.button.call_args.kwargs["disabled"] is True
    on_retry.assert_not_called()


def test_render_chat_message_keeps_sql_table_and_csv_download(streamlit):
    result = pd.DataFrame({"cliente": ["Ana"], "total": [3]})
    message = {
        "role": "assistant",
        "content": "Resultado da consulta.",
        "sql": "SELECT cliente, total FROM clientes",
        "df": result,
    }

    components.render_chat_message(0, message)

    assert streamlit.chat_message.call_count == 1
    assert streamlit.code.call_args.kwargs == {"language": "sql"}
    assert streamlit.code.call_args.args == (message["sql"],)
    assert streamlit.dataframe.call_args.args == (result,)
    assert streamlit.download_button.call_args.kwargs["data"] == result.to_csv(
        index=False
    ).encode("utf-8")


def test_render_chat_message_shows_associated_sql_and_error_once(streamlit):
    message = {
        "role": "assistant",
        "content": "A consulta falhou.",
        "sql": "SELECT * FROM missing_table",
        "error": "Tabela inexistente.",
    }

    components.render_chat_message(0, message)

    assert streamlit.chat_message.call_count == 1
    assert streamlit.write.call_args.args == ("A consulta falhou.",)
    assert streamlit.code.call_args.args == ("SELECT * FROM missing_table",)
    assert streamlit.error.call_args.args == ("Tabela inexistente.",)
    assert streamlit.error.call_count == 1


def test_chart_button_does_not_force_a_second_rerun(streamlit):
    streamlit.button.return_value = True
    result = pd.DataFrame({"mes": ["jan"], "total": [4]})
    message = {
        "role": "assistant",
        "content": "Resultado.",
        "df": result,
        "grafico": {"tipo": "bar", "eixo_x": "mes", "eixo_y": "total"},
    }

    components.render_chat_message(0, message)

    assert message["show_chart"] is True
    assert streamlit.bar_chart.call_args.kwargs == {"x": "mes", "y": "total"}
    streamlit.rerun.assert_not_called()


def test_pending_review_is_a_distinct_action_card_not_a_chat_transcript_message(streamlit):
    streamlit.session_state.pending_sql = "SELECT 1"
    db = MagicMock()

    components.render_pending_sql(db)

    streamlit.container.assert_called_once_with(border=True)
    streamlit.chat_message.assert_not_called()
    streamlit.code.assert_called_once_with("SELECT 1", language="sql")
    db.execute_query.assert_not_called()


def test_pending_query_failure_is_added_once_to_transcript(streamlit):
    streamlit.button.return_value = True
    streamlit.session_state.pending_sql = "SELECT * FROM missing_table"
    streamlit.session_state.pending_prompt = "Quantos registros?"
    db = MagicMock()
    db.execute_query.side_effect = RuntimeError("Tabela inexistente.")

    components.render_pending_sql(db)

    assert streamlit.session_state.messages == [
        {
            "role": "assistant",
            "content": "Houve um problema ao executar a consulta.",
            "sql": "SELECT * FROM missing_table",
            "error": "Tabela inexistente.",
        }
    ]
    assert streamlit.error.call_count == 0
    streamlit.rerun.assert_called_once_with()
