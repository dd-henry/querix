import logging

from fastapi import HTTPException, Query
from fastapi.testclient import TestClient

from api.app import APIError, create_app
from api.config import Settings


def _settings(**overrides):
    values = {
        "web_origin": "http://localhost:5173",
        "session_secret": "test-secret",
    }
    values.update(overrides)
    return Settings(**values)


def test_create_app_does_not_initialize_external_services():
    services = object()

    app = create_app(_settings(), services=services)

    assert app.state.settings.web_origin == "http://localhost:5173"
    assert app.state.services is services


def test_health_endpoint_is_available_without_external_services():
    app = create_app(_settings())

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_errors_use_the_documented_envelope():
    app = create_app(_settings())

    @app.get("/validation")
    def validation(value: int = Query(...)):
        return {"value": value}

    @app.get("/auth")
    def auth_error():
        raise APIError(401, "auth_required", "Authentication required.")

    @app.get("/missing")
    def missing():
        raise HTTPException(status_code=404, detail="Record not found.")

    @app.get("/conflict")
    def conflict():
        raise HTTPException(
            status_code=409,
            detail={"code": "conflict", "message": "Resource conflict."},
        )

    @app.get("/unexpected")
    def unexpected():
        raise RuntimeError("sensitive internal details")

    client = TestClient(app, raise_server_exceptions=False)

    validation_response = client.get("/validation", params={"value": "invalid"})
    assert validation_response.status_code == 422
    assert validation_response.json() == {
        "error": {
            "code": "validation_error",
            "message": "Request validation failed.",
        }
    }

    auth_response = client.get("/auth")
    assert auth_response.status_code == 401
    assert auth_response.json() == {
        "error": {
            "code": "auth_required",
            "message": "Authentication required.",
        }
    }

    not_found_response = client.get("/missing")
    assert not_found_response.status_code == 404
    assert not_found_response.json() == {
        "error": {"code": "not_found", "message": "Record not found."}
    }

    conflict_response = client.get("/conflict")
    assert conflict_response.status_code == 409
    assert conflict_response.json() == {
        "error": {"code": "conflict", "message": "Resource conflict."}
    }

    unexpected_response = client.get("/unexpected")
    assert unexpected_response.status_code == 500
    assert unexpected_response.json() == {
        "error": {
            "code": "internal_error",
            "message": "Internal server error.",
        }
    }


def test_mutating_origins_are_restricted_and_allowed_origin_gets_cors_headers():
    app = create_app(_settings())

    @app.post("/mutate")
    def mutate():
        return {"ok": True}

    client = TestClient(app)

    rejected = client.post(
        "/mutate",
        headers={"Origin": "https://evil.example"},
    )
    assert rejected.status_code == 403
    assert rejected.json() == {
        "error": {
            "code": "origin_not_allowed",
            "message": "Request origin is not allowed.",
        }
    }

    allowed = client.post(
        "/mutate",
        headers={"Origin": "http://localhost:5173"},
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert allowed.headers["access-control-allow-credentials"] == "true"


def test_request_logs_exclude_payload_secrets_and_rows(caplog):
    app = create_app(_settings())

    @app.post("/echo")
    def echo(payload: dict):
        return payload

    password = "password-that-must-not-be-logged"
    cookie = "cookie-that-must-not-be-logged"
    sql = "SELECT secret FROM private_table"
    row = "private-row-value"

    client = TestClient(app)
    client.cookies.set("session", cookie)
    with caplog.at_level(logging.INFO, logger="api.app"):
        response = client.post(
            "/echo",
            json={"password": password, "sql": sql, "rows": [row]},
        )

    assert response.status_code == 200
    assert "api_request method=POST path=/echo status=200" in caplog.text
    assert password not in caplog.text
    assert cookie not in caplog.text
    assert sql not in caplog.text
    assert row not in caplog.text
