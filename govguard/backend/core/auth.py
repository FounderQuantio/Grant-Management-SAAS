"""
GovGuard™ — Authentication & RBAC
Cognito JWT validation with role-based access control.
"""
import hashlib
import time
from functools import lru_cache
from typing import Optional
from uuid import UUID

import httpx
import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwk, jwt
from pydantic import BaseModel

from core.config import settings
from core.exceptions import AuthenticationError, AuthorizationError

log = structlog.get_logger()

security = HTTPBearer(auto_error=False)

ROLES = {
    "system_admin": 7,
    "agency_officer": 6,
    "compliance_officer": 5,
    "finance_manager": 4,
    "finance_staff": 3,
    "auditor": 2,
    "equity_analyst": 1,
}

# Endpoint → minimum required role
PERMISSION_MAP: dict[str, dict[str, str]] = {
    "/api/v1/tenants": {"POST": "system_admin", "GET": "system_admin", "PATCH": "system_admin"},
    "/api/v1/users/invite": {"POST": "compliance_officer"},
    "/api/v1/users": {"GET": "compliance_officer"},
    "/api/v1/grants": {"POST": "compliance_officer", "GET": "finance_staff"},
    "/api/v1/transactions": {"POST": "finance_manager", "GET": "finance_staff"},
    "/api/v1/compliance/controls": {"GET": "finance_staff", "PATCH": "compliance_officer"},
    "/api/v1/compliance/run": {"POST": "compliance_officer"},
    "/api/v1/fraud/screen": {"POST": "agency_officer"},
    "/api/v1/fraud/vendors": {"GET": "compliance_officer"},
    "/api/v1/audit/findings": {"GET": "compliance_officer"},
    "/api/v1/audit/cap": {"POST": "compliance_officer", "PATCH": "compliance_officer"},
    "/api/v1/dashboard/kpis": {"GET": "finance_staff"},
}


class UserContext(BaseModel):
    id: UUID
    tenant_id: UUID
    cognito_sub: str
    role: str
    display_name: str
    email_hash: str


class JWKSCache:
    _keys: Optional[dict] = None
    _fetched_at: float = 0
    _ttl: float = 3600

    @classmethod
    async def get_keys(cls) -> dict:
        if cls._keys is None or (time.time() - cls._fetched_at) > cls._ttl:
            async with httpx.AsyncClient() as client:
                resp = await client.get(settings.cognito_jwks_url, timeout=10)
                resp.raise_for_status()
                cls._keys = {k["kid"]: k for k in resp.json()["keys"]}
                cls._fetched_at = time.time()
        return cls._keys


async def decode_cognito_jwt(token: str) -> dict:
    """Decode and verify Cognito JWT, return claims."""
    try:
        header = jwt.get_unverified_header(token)
        keys = await JWKSCache.get_keys()
        kid = header.get("kid")
        if kid not in keys:
            raise AuthenticationError("JWT key ID not found in JWKS")
        public_key = jwk.construct(keys[kid])
        claims = jwt.decode(
            token,
            public_key,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.COGNITO_CLIENT_ID,
        )
        return claims
    except JWTError as e:
        raise AuthenticationError(f"JWT validation failed: {e}")


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> UserContext:
    """FastAPI dependency: validate JWT and return user context."""
    token = None

    # Try Authorization header first, then cookie
    if credentials:
        token = credentials.credentials
    elif "gg_access" in request.cookies:
        token = request.cookies["gg_access"]

    if not token:
        raise AuthenticationError("No authentication token provided")

    claims = await decode_cognito_jwt(token)

    # Extract custom claims added by Cognito Pre-Token Lambda
    tenant_id = claims.get("custom:tenant_id")
    role = claims.get("custom:role", "finance_staff")
    user_id = claims.get("custom:user_id")

    if not tenant_id or not user_id:
        raise AuthenticationError("Token missing required claims")

    user = UserContext(
        id=UUID(user_id),
        tenant_id=UUID(tenant_id),
        cognito_sub=claims["sub"],
        role=role,
        display_name=claims.get("name", ""),
        email_hash=hashlib.sha256(claims.get("email", "").encode()).hexdigest(),
    )

    # Attach to request state for middleware access
    request.state.user = user
    request.state.tenant_id = str(tenant_id)

    return user


def require_role(*roles: str):
    """Dependency factory: enforce minimum role requirement."""
    async def _check(user: UserContext = Depends(get_current_user)) -> UserContext:
        user_level = ROLES.get(user.role, 0)
        required_level = max(ROLES.get(r, 0) for r in roles)
        if user_level < required_level:
            raise AuthorizationError(
                f"Role '{user.role}' insufficient. Required: {roles}"
            )
        return user
    return _check


# Shorthand dependencies
RequireSystemAdmin = Depends(require_role("system_admin"))
RequireAgencyOfficer = Depends(require_role("agency_officer"))
RequireComplianceOfficer = Depends(require_role("compliance_officer"))
RequireFinanceManager = Depends(require_role("finance_manager"))
RequireAnyRole = Depends(get_current_user)
