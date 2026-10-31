from typing import Dict

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from api.app import APIError
from api.auth.service import (
    AuthConfigurationError,
    AuthServiceError,
    SupabaseAuthService,
)
from api.auth.session import SessionClaims, clear_session, issue_session
from api.config import Settings
from api.dependencies import (
    get_api_settings,
    get_current_session,
    get_user_repository,
    require_approved_user,
)
from database.users import UserRepository

router = APIRouter()

SIGNUP_SUCCESS_MESSAGE = (
    "Cadastro recebido. Confirme seu email e aguarde a aprovação de um admin."
)
_STATUS_MESSAGES = {
    "pending": "Sua conta aguarda aprovação.",
    "rejected": "Sua solicitação de acesso foi rejeitada.",
    "disabled": "Sua conta está desativada.",
}


class LoginRequest(BaseModel):
    email: str
    password: str


class SignupRequest(BaseModel):
    name: str
    email: str
    password: str
    password_confirmation: str


class ProfileResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    status: str


class SignupResponse(BaseModel):
    message: str


def get_auth_service(
    settings: Settings = Depends(get_api_settings),
) -> SupabaseAuthService:
    try:
        return SupabaseAuthService(settings)
    except AuthConfigurationError as exc:
        raise APIError(
            503,
            "auth_not_configured",
            str(exc),
        ) from exc


def _profile_response(profile: Dict[str, object]) -> ProfileResponse:
    try:
        return ProfileResponse(
            id=str(profile["id"]),
            email=str(profile["email"]),
            name=str(profile["name"]),
            role=str(profile["role"]),
            status=str(profile["status"]),
        )
    except KeyError as exc:
        raise APIError(
            500,
            "invalid_profile",
            "The authenticated profile is incomplete.",
        ) from exc


def _raise_auth_failure(error: AuthServiceError) -> None:
    status_code = 401 if error.code == "auth_failed" else 502
    raise APIError(status_code, error.code, error.message) from error


def _require_approved_profile(profile: Dict[str, object]) -> None:
    if profile.get("status") != "approved":
        status = str(profile.get("status"))
        raise APIError(
            403,
            "account_not_approved",
            _STATUS_MESSAGES.get(status, "Sua conta não está aprovada."),
        )


@router.post("/login", response_model=ProfileResponse)
def login(
    payload: LoginRequest,
    response: Response,
    settings: Settings = Depends(get_api_settings),
    auth_service: SupabaseAuthService = Depends(get_auth_service),
    repository: UserRepository = Depends(get_user_repository),
) -> ProfileResponse:
    try:
        identity = auth_service.sign_in(payload.email, payload.password)
    except AuthServiceError as exc:
        _raise_auth_failure(exc)

    profile = repository.get_profile(identity.id)
    if profile is None:
        raise APIError(
            403,
            "account_not_approved",
            "No approved profile is available for this account.",
        )
    _require_approved_profile(profile)
    issue_session(response, identity.id, settings)
    return _profile_response(profile)


@router.post("/signup", response_model=SignupResponse)
def signup(
    payload: SignupRequest,
    auth_service: SupabaseAuthService = Depends(get_auth_service),
    repository: UserRepository = Depends(get_user_repository),
) -> SignupResponse:
    name = payload.name.strip()
    email = payload.email.strip()
    if not name or not email:
        raise APIError(422, "validation_error", "Name and email are required.")
    if len(payload.password) < 8:
        raise APIError(
            422,
            "validation_error",
            "Password must contain at least 8 characters.",
        )
    if payload.password != payload.password_confirmation:
        raise APIError(
            422,
            "validation_error",
            "Password confirmation does not match.",
        )

    try:
        identity = auth_service.sign_up(email, payload.password, name)
    except AuthServiceError as exc:
        _raise_auth_failure(exc)

    repository.create_pending_profile(
        identity.id,
        identity.email or email,
        name,
    )
    return SignupResponse(message=SIGNUP_SUCCESS_MESSAGE)


@router.post("/logout")
def logout(
    response: Response,
    _session: SessionClaims = Depends(get_current_session),
):
    clear_session(response)
    return {"message": "Logged out."}


@router.get("/me", response_model=ProfileResponse)
def current_user(
    profile: Dict[str, object] = Depends(require_approved_user),
) -> ProfileResponse:
    return _profile_response(profile)
