"""GovGuard™ — FastAPI Application Factory"""
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.config import settings
from core.db import init_db, close_db
from core.cache import init_redis, close_redis
from core.exceptions import GovGuardException
from core.middleware import TenantMiddleware, RateLimitMiddleware, AuditLogMiddleware, RequestIDMiddleware

from modules.auth.router import router as auth_router
from modules.tenants.router import router as tenants_router
from modules.users.router import router as users_router
from modules.grants.router import router as grants_router
from modules.transactions.router import router as transactions_router
from modules.compliance_engine.router import router as compliance_router
from modules.payment_integrity.router import router as payment_router
from modules.pre_award.router import router as pre_award_router
from modules.audit_hub.router import router as audit_router
from modules.dashboard.router import router as dashboard_router
from modules.erp_integration.router import router as erp_router
from modules.webhooks.router import router as webhooks_router

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    log.info("govguard.startup", env=settings.ENVIRONMENT)
    await init_db()
    await init_redis()
    yield
    await close_db()
    await close_redis()
    log.info("govguard.shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="GovGuard™ Enterprise Platform",
        version="1.0.0",
        docs_url="/api/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.ENVIRONMENT != "production" else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Tenant-ID"],
        expose_headers=["X-Request-ID", "X-Tenant-ID"],
    )

    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(AuditLogMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(TenantMiddleware)

    @app.exception_handler(GovGuardException)
    async def govguard_exc_handler(request: Request, exc: GovGuardException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error_code": exc.error_code,
                "message": exc.message,
                "request_id": getattr(request.state, "request_id", "unknown"),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "details": exc.details or {},
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exc_handler(request: Request, exc: Exception) -> JSONResponse:
        log.error("unhandled_exception", exc=str(exc), path=str(request.url))
        return JSONResponse(
            status_code=500,
            content={
                "error_code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
                "request_id": getattr(request.state, "request_id", "unknown"),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "details": {},
            },
        )

    @app.get("/health", include_in_schema=False)
    async def health() -> dict:
        return {"status": "ok", "version": "1.0.0"}

    PREFIX = "/api/v1"
    app.include_router(auth_router,         prefix=f"{PREFIX}/auth",         tags=["Auth"])
    app.include_router(tenants_router,      prefix=f"{PREFIX}/tenants",      tags=["Tenants"])
    app.include_router(users_router,        prefix=f"{PREFIX}/users",        tags=["Users"])
    app.include_router(grants_router,       prefix=f"{PREFIX}/grants",       tags=["Grants"])
    app.include_router(transactions_router, prefix=f"{PREFIX}/transactions", tags=["Transactions"])
    app.include_router(compliance_router,   prefix=f"{PREFIX}/compliance",   tags=["Compliance"])
    app.include_router(payment_router,      prefix=f"{PREFIX}/fraud",        tags=["Fraud"])
    app.include_router(pre_award_router,    prefix=f"{PREFIX}/fraud",        tags=["Fraud"])
    app.include_router(audit_router,        prefix=f"{PREFIX}/audit",        tags=["Audit"])
    app.include_router(dashboard_router,    prefix=f"{PREFIX}/dashboard",    tags=["Dashboard"])
    app.include_router(erp_router,          prefix=f"{PREFIX}/integrations", tags=["Integrations"])
    app.include_router(webhooks_router,     prefix=f"{PREFIX}/webhooks",     tags=["Webhooks"])

    return app


app = create_app()
