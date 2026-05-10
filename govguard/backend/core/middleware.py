"""
GovGuard™ — Middleware Stack
Execution order: RequestID → Tenant → RateLimit → AuditLog
"""
import hashlib
import json
import time
import uuid
from typing import Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from core.config import settings

log = structlog.get_logger()
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attaches a unique X-Request-ID to every request."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID", f"req_{uuid.uuid4().hex[:16]}")
        request.state.request_id = request_id
        request.state.start_time = time.time()

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{(time.time() - request.state.start_time) * 1000:.2f}ms"
        return response


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Injects tenant context from JWT claim into request state.
    The actual PostgreSQL SET LOCAL is done per-session in the DB dependency.
    """

    SKIP_PATHS = {"/health", "/api/v1/auth/token", "/api/v1/webhooks/stripe"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        # tenant_id is set by get_current_user() auth dependency
        # This middleware just ensures it's accessible on request.state
        if not hasattr(request.state, "tenant_id"):
            request.state.tenant_id = None

        response = await call_next(request)

        tenant_id = getattr(request.state, "tenant_id", None)
        if tenant_id:
            response.headers["X-Tenant-ID"] = str(tenant_id)

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Redis-backed rate limiting: 1000 req/min per tenant_id.
    Falls back to IP-based limiting for unauthenticated requests.
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self._redis = None

    async def _get_redis(self):
        if self._redis is None:
            from core.cache import redis_client
            self._redis = redis_client
        return self._redis

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        from fastapi.responses import JSONResponse
        from core.exceptions import RateLimitError

        redis = await self._get_redis()
        tenant_id = getattr(request.state, "tenant_id", None)
        key_suffix = tenant_id or request.client.host
        rate_key = f"ratelimit:{key_suffix}"

        try:
            count = await redis.incr(rate_key)
            if count == 1:
                await redis.expire(rate_key, 60)
            if count > settings.RATE_LIMIT_PER_MINUTE:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error_code": "RATE_LIMIT_EXCEEDED",
                        "message": "Rate limit exceeded. Retry after 60 seconds.",
                        "request_id": getattr(request.state, "request_id", "unknown"),
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "details": {},
                    },
                )
        except Exception:
            pass  # Never block requests due to Redis failure

        return await call_next(request)


class AuditLogMiddleware(BaseHTTPMiddleware):
    """
    Writes audit_events record after every mutating request (POST/PUT/PATCH/DELETE).
    Runs AFTER the route handler so we have access to response status.
    """

    SKIP_PATHS = {"/health", "/api/v1/auth/token", "/api/v1/auth/refresh"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        if (
            request.method in MUTATING_METHODS
            and request.url.path not in self.SKIP_PATHS
            and response.status_code < 400
            and hasattr(request.state, "user")
        ):
            try:
                await self._write_audit_event(request, response)
            except Exception as e:
                log.warning("audit_log_failed", error=str(e), path=request.url.path)

        return response

    async def _write_audit_event(self, request: Request, response: Response) -> None:
        from core.db import AsyncSessionLocal
        from sqlalchemy import text

        user = request.state.user
        path_parts = request.url.path.strip("/").split("/")
        resource_type = path_parts[3] if len(path_parts) > 3 else "unknown"
        resource_id = path_parts[4] if len(path_parts) > 4 else None

        async with AsyncSessionLocal() as session:
            await session.execute(text("SET LOCAL app.current_tenant = :tid"), {"tid": str(user.tenant_id)})
            await session.execute(
                text("""
                    INSERT INTO audit_events
                        (tenant_id, user_id, action, resource_type, resource_id, 
                         new_value_hash, ip_address)
                    VALUES
                        (:tenant_id, :user_id, :action, :resource_type, :resource_id,
                         :new_value_hash, :ip_address)
                """),
                {
                    "tenant_id": str(user.tenant_id),
                    "user_id": str(user.id),
                    "action": f"{request.method}:{resource_type.upper()}",
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "new_value_hash": hashlib.sha256(
                        f"{request.url.path}:{time.time()}".encode()
                    ).hexdigest(),
                    "ip_address": request.client.host if request.client else None,
                },
            )
            await session.commit()
