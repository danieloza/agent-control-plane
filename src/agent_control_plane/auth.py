from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Header, HTTPException, Request
from fastapi.security.utils import get_authorization_scheme_param

from .settings import Settings, get_settings


@dataclass(frozen=True, slots=True)
class OperatorProfile:
    id: str
    label: str
    role: str
    tenant_scope: list[str]
    permissions: list[str]


@dataclass(frozen=True, slots=True)
class AuthContext:
    username: str
    profile: OperatorProfile


PROFILES: dict[str, OperatorProfile] = {
    "ops-supervisor": OperatorProfile(
        id="ops-supervisor",
        label="Ops Supervisor",
        role="operator",
        tenant_scope=["acme-support", "acme-ops"],
        permissions=["review", "approve", "replay"],
    ),
    "security-lead": OperatorProfile(
        id="security-lead",
        label="Security Lead",
        role="security",
        tenant_scope=["acme-finance", "acme-ops"],
        permissions=["review", "contain_incident", "replay", "assign_owner"],
    ),
    "platform-admin": OperatorProfile(
        id="platform-admin",
        label="Platform Admin",
        role="admin",
        tenant_scope=["acme-support", "acme-ops", "acme-finance"],
        permissions=["review", "approve", "replay", "contain_incident", "assign_owner", "admin"],
    ),
}

DEMO_USERS = {
    "ops.demo": {"password": "ops-demo", "profile_id": "ops-supervisor"},
    "security.demo": {"password": "security-demo", "profile_id": "security-lead"},
    "admin.demo": {"password": "admin-demo", "profile_id": "platform-admin"},
}


def create_access_token(username: str, profile_id: str, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": username,
        "profile_id": profile_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_exp_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def authenticate_demo_user(username: str, password: str) -> AuthContext:
    record = DEMO_USERS.get(username)
    if record is None or record["password"] != password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    profile = PROFILES[record["profile_id"]]
    return AuthContext(username=username, profile=profile)


def _resolve_token_context(token: str, settings: Settings) -> AuthContext:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:  # pragma: no cover
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    username = payload.get("sub")
    profile_id = payload.get("profile_id")
    profile = PROFILES.get(profile_id)
    if not username or profile is None:
        raise HTTPException(status_code=401, detail="Invalid token claims")
    return AuthContext(username=username, profile=profile)


def get_auth_context(
    request: Request,
    x_operator_profile: str | None = Header(default=None, alias="X-Operator-Profile"),
) -> AuthContext:
    settings: Settings = request.app.state.settings
    authorization = request.headers.get("Authorization")
    scheme, credentials = get_authorization_scheme_param(authorization)
    if scheme.lower() == "bearer" and credentials:
        return _resolve_token_context(credentials, settings)
    profile_id = x_operator_profile or settings.default_operator_profile
    profile = PROFILES.get(profile_id)
    if not profile:
        raise HTTPException(status_code=401, detail="Unknown operator profile")
    return AuthContext(username=profile.id, profile=profile)


def require_permission(context: AuthContext, permission: str) -> None:
    if permission not in context.profile.permissions:
        raise HTTPException(status_code=403, detail=f"Profile '{context.profile.id}' lacks '{permission}' permission")


def require_tenant_access(context: AuthContext, tenant: str) -> None:
    if tenant not in context.profile.tenant_scope:
        raise HTTPException(status_code=403, detail=f"Profile '{context.profile.id}' cannot access tenant '{tenant}'")
