import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.health import router as health_router
from backend.app.api.v1 import api_v1_router
from backend.app.core.config import settings
from backend.app.core.logging import setup_logging
from backend.app.core.middleware import RequestContextMiddleware

logger = setup_logging(debug=settings.DEBUG)


async def ensure_default_seed() -> None:
    """Ensures default tenant and admin user exist for foreign key integrity."""
    import uuid
    from sqlalchemy import text
    from backend.app.db.models import Membership, Tenant, User, UserRole
    from backend.app.db.session import AsyncSessionLocal

    default_tenant_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    default_user_id = uuid.UUID("22222222-2222-2222-2222-222222222222")

    try:
        async with AsyncSessionLocal() as session:
            res = await session.execute(
                text("SELECT id FROM tenants WHERE id = :tenant_id"),
                {"tenant_id": default_tenant_id},
            )
            if not res.scalar_one_or_none():
                tenant = Tenant(
                    id=default_tenant_id,
                    name="Default Organization",
                    slug="default-org",
                    is_active=True,
                )
                session.add(tenant)
                await session.commit()
                logger.info("Default tenant seeded: %s", default_tenant_id)

            res_user = await session.execute(
                text("SELECT id FROM users WHERE id = :user_id"),
                {"user_id": default_user_id},
            )
            if not res_user.scalar_one_or_none():
                user = User(
                    id=default_user_id,
                    email="admin@docvane.local",
                    hashed_password="hashed_placeholder",
                    full_name="DocVane Admin",
                    is_active=True,
                    is_superuser=True,
                )
                session.add(user)
                await session.commit()
                logger.info("Default user seeded: %s", default_user_id)

            res_mem = await session.execute(
                text(
                    "SELECT id FROM memberships WHERE tenant_id = :tenant_id AND user_id = :user_id"
                ),
                {"tenant_id": default_tenant_id, "user_id": default_user_id},
            )
            if not res_mem.scalar_one_or_none():
                mem = Membership(
                    id=uuid.uuid4(),
                    tenant_id=default_tenant_id,
                    user_id=default_user_id,
                    role=UserRole.OWNER,
                )
                session.add(mem)
                await session.commit()
                logger.info("Default membership seeded.")
    except Exception as exc:
        logger.warning("Could not execute default seed check: %s", exc)


def setup_observability() -> None:
    """Configures Langfuse LLM tracing and observability if keys are provided."""
    public_key = settings.LANGFUSE_PUBLIC_KEY or os.environ.get("LANGFUSE_PUBLIC_KEY", "")
    secret_key = settings.LANGFUSE_SECRET_KEY or os.environ.get("LANGFUSE_SECRET_KEY", "")
    host = (
        settings.LANGFUSE_BASE_URL
        or settings.LANGFUSE_HOST
        or os.environ.get("LANGFUSE_BASE_URL", "")
        or os.environ.get("LANGFUSE_HOST", "")
        or "https://cloud.langfuse.com"
    )

    if public_key and secret_key:
        try:
            import litellm

            os.environ["LANGFUSE_PUBLIC_KEY"] = public_key
            os.environ["LANGFUSE_SECRET_KEY"] = secret_key
            os.environ["LANGFUSE_HOST"] = host
            os.environ["LANGFUSE_BASE_URL"] = host

            if not isinstance(litellm.success_callback, list):
                litellm.success_callback = []
            if "langfuse" not in litellm.success_callback:
                litellm.success_callback.append("langfuse")

            if not isinstance(litellm.failure_callback, list):
                litellm.failure_callback = []
            if "langfuse" not in litellm.failure_callback:
                litellm.failure_callback.append("langfuse")

            logger.info("Langfuse LLM observability enabled for LiteLLM (host=%s).", host)
        except Exception as e:
            logger.warning("Could not initialize Langfuse callback: %s", e)
    else:
        logger.info("Langfuse keys not provided. LLM tracing is inactive.")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info(f"Starting {settings.PROJECT_NAME} in [{settings.ENVIRONMENT}] mode...")
    setup_observability()
    await ensure_default_seed()
    yield
    logger.info(f"Shutting down {settings.PROJECT_NAME}")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="0.1.0",
        description="Docvane",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    app.add_middleware(RequestContextMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(api_v1_router, prefix=settings.API_V1_STR)

    return app


app = create_app()
