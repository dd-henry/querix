from datetime import datetime, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from api.schemas.conversations import (
    ConversationDetailResponse,
    ConversationGroupSchema,
    ConversationMessageSchema,
    ConversationNotFoundResponse,
    ConversationSummarySchema,
    MessageMetadata,
    ProfileSchema,
)


USER_ID = UUID("00000000-0000-0000-0000-000000000001")
SESSION_ID = UUID("00000000-0000-0000-0000-000000000002")
REQUEST_ID = UUID("00000000-0000-0000-0000-000000000003")
CREATED_AT = datetime(2025, 1, 2, 12, 30, tzinfo=timezone.utc)


def test_profile_and_conversation_schemas_validate_required_fields():
    profile = ProfileSchema(
        id=USER_ID,
        email="user@example.com",
        name="User",
        role="user",
        status="approved",
    )
    conversation = ConversationSummarySchema(
        id=SESSION_ID,
        title="Revenue",
        created_at=CREATED_AT,
        last_activity=CREATED_AT,
    )
    detail = ConversationDetailResponse(
        **conversation.model_dump(),
        messages=[
            ConversationMessageSchema(
                id=1,
                request_id=REQUEST_ID,
                role="user",
                content="Show revenue",
                created_at=CREATED_AT,
            )
        ],
    )

    assert profile.role == "user"
    assert detail.messages[0].role == "user"
    assert detail.messages[0].sql is None
    assert detail.messages[0].error is None


def test_message_schema_requires_ordering_and_identity_fields():
    with pytest.raises(ValidationError):
        ConversationMessageSchema(
            id=1,
            role="assistant",
            content="Answer",
            created_at=CREATED_AT,
        )


def test_metadata_preserves_retry_and_extended_result_data():
    metadata = MessageMetadata(
        retryable=True,
        retry_kind="execute",
        result={"columns": ["total"], "rows": []},
    )
    message = ConversationMessageSchema(
        id=2,
        request_id=REQUEST_ID,
        role="assistant",
        content="Done",
        sql="SELECT 1",
        metadata=metadata,
        created_at=CREATED_AT,
    )

    assert message.metadata.retryable is True
    assert message.metadata.retry_kind == "execute"
    assert message.metadata.model_extra == {
        "result": {"columns": ["total"], "rows": []}
    }


def test_group_and_not_found_schemas_have_stable_json_dates_and_error_shape():
    group = ConversationGroupSchema(
        key="today",
        label="Hoje",
        conversations=[
            ConversationSummarySchema(
                id=SESSION_ID,
                title="Revenue",
                is_favorite=True,
                created_at=CREATED_AT,
                last_activity=CREATED_AT,
            )
        ],
    )
    not_found = ConversationNotFoundResponse()

    payload = group.model_dump(mode="json")

    assert payload["conversations"][0]["last_activity"] == "2025-01-02T12:30:00Z"
    assert not_found.model_dump(mode="json") == {
        "error": {
            "code": "not_found",
            "message": "Conversation not found.",
        }
    }
