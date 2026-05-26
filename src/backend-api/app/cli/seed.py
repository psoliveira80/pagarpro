"""Seed script: creates default roles and admin user.

Usage: python -m app.cli.seed
"""

import asyncio
import os
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_sessionmaker
from app.infrastructure.db.models.user import User, Role, UserRole
from app.infrastructure.security.password_hasher import hash_password


ROLES = ["Admin", "Operador", "Validador", "Auditor"]

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_INITIAL_PASSWORD", "Admin@123")
ADMIN_FULL_NAME = "Administrador"


async def _get_empresa_id(session: AsyncSession) -> UUID:
    """Fetch the first empresa_id from comercial.empresas."""
    row = (await session.execute(text("SELECT id FROM comercial.empresas LIMIT 1"))).first()
    if row is None:
        raise RuntimeError("No empresa found in comercial.empresas — run migrations first.")
    return row[0]


async def seed() -> None:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        async with session.begin():
            empresa_id = await _get_empresa_id(session)
            await _seed_roles(session, empresa_id)
            await _seed_admin(session, empresa_id)
    print("Seed completed successfully.")


async def _seed_roles(session: AsyncSession, empresa_id: UUID) -> None:
    for role_name in ROLES:
        existing = await session.execute(
            select(Role).where(Role.nome == role_name)
        )
        if existing.scalar_one_or_none() is None:
            session.add(Role(nome=role_name, descricao=f"Role: {role_name}"))
            print(f"  Created role: {role_name}")
        else:
            print(f"  Role exists: {role_name}")


async def _seed_admin(session: AsyncSession, empresa_id: UUID) -> None:
    existing = await session.execute(
        select(User).where(User.email == ADMIN_EMAIL)
    )
    if existing.scalar_one_or_none() is not None:
        print(f"  Admin user exists: {ADMIN_EMAIL}")
        return

    user = User(
        empresa_id=empresa_id,
        email=ADMIN_EMAIL,
        senha_hash=hash_password(ADMIN_PASSWORD),
        nome_completo=ADMIN_FULL_NAME,
        ativo=True,
    )
    session.add(user)
    await session.flush()

    admin_role = await session.execute(
        select(Role).where(Role.nome == "Admin")
    )
    role = admin_role.scalar_one()
    session.add(UserRole(usuario_id=user.id, perfil_id=role.id, empresa_id=empresa_id))
    print(f"  Created admin user: {ADMIN_EMAIL} (linked to Admin role)")


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
