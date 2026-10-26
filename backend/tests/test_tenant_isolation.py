import uuid

import pytest
from sqlalchemy import select, text

from backend.app.db.models import Document, DocumentStatus, Tenant
from backend.app.db.session import AsyncSessionLocal, engine


@pytest.fixture(autouse=True)
async def setup_app_role() -> None:
    """Creates a non-superuser application role to test PostgreSQL RLS enforcement."""
    async with engine.connect() as conn:
        await conn.execute(
            text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'docvane_app') THEN
                    CREATE ROLE docvane_app WITH LOGIN PASSWORD 'docvane_app'
                    NOSUPERUSER NOCREATEDB NOCREATEROLE;
                END IF;
            END
            $$;
            """)
        )
        await conn.execute(text("GRANT ALL ON ALL TABLES IN SCHEMA public TO docvane_app;"))
        await conn.execute(text("GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO docvane_app;"))
        await conn.commit()


@pytest.mark.asyncio
async def test_tenant_rls_isolation() -> None:
    """
    CRITICAL PHASE 0 TEST:
    Proves that PostgreSQL Row-Level Security (RLS) strictly prevents Tenant A
    from viewing Tenant B rows, enforced at the database engine level.
    """
    tenant_a_id = uuid.uuid4()
    tenant_b_id = uuid.uuid4()

    # Step 1: Seed data for two separate tenants
    async with AsyncSessionLocal() as session:
        tenant_a = Tenant(
            id=tenant_a_id,
            name="Company Alpha",
            slug=f"alpha-{uuid.uuid4().hex[:6]}",
        )
        tenant_b = Tenant(
            id=tenant_b_id,
            name="Company Beta",
            slug=f"beta-{uuid.uuid4().hex[:6]}",
        )
        session.add_all([tenant_a, tenant_b])
        await session.commit()

        # Document for Tenant A
        doc_a = Document(
            id=uuid.uuid4(),
            tenant_id=tenant_a_id,
            filename="alpha_secret_contract.pdf",
            file_type="pdf",
            status=DocumentStatus.READY,
            storage_key=f"{tenant_a_id}/alpha_secret_contract.pdf",
            checksum="a" * 64,
            file_size_bytes=1024,
            page_count=2,
        )

        # Document for Tenant B
        doc_b = Document(
            id=uuid.uuid4(),
            tenant_id=tenant_b_id,
            filename="beta_confidential_invoice.pdf",
            file_type="pdf",
            status=DocumentStatus.READY,
            storage_key=f"{tenant_b_id}/beta_confidential_invoice.pdf",
            checksum="b" * 64,
            file_size_bytes=2048,
            page_count=1,
        )

        session.add_all([doc_a, doc_b])
        await session.commit()

    # TEST CASE 1: Query as Tenant A (using non-superuser app role)
    async with AsyncSessionLocal() as session:
        await session.execute(text("SET ROLE docvane_app;"))
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
            {"tenant_id": str(tenant_a_id)},
        )

        result = await session.execute(select(Document))
        docs = result.scalars().all()

        assert len(docs) == 1
        assert docs[0].tenant_id == tenant_a_id
        assert docs[0].filename == "alpha_secret_contract.pdf"
        await session.execute(text("RESET ROLE;"))

    # TEST CASE 2: Query as Tenant B
    async with AsyncSessionLocal() as session:
        await session.execute(text("SET ROLE docvane_app;"))
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
            {"tenant_id": str(tenant_b_id)},
        )

        result = await session.execute(select(Document))
        docs = result.scalars().all()

        assert len(docs) == 1
        assert docs[0].tenant_id == tenant_b_id
        assert docs[0].filename == "beta_confidential_invoice.pdf"
        await session.execute(text("RESET ROLE;"))

    # TEST CASE 3: Query without tenant context (unauthenticated / empty)
    async with AsyncSessionLocal() as session:
        await session.execute(text("SET ROLE docvane_app;"))
        await session.execute(text("SELECT set_config('app.current_tenant_id', '', false)"))

        result = await session.execute(select(Document))
        docs = result.scalars().all()

        # RLS must block all rows when no valid tenant is active
        assert len(docs) == 0
        await session.execute(text("RESET ROLE;"))
