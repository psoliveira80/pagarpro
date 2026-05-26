# Backward-compat shim — story 12.3 will update all direct imports.
# Tables renamed in migration 0015: users→acesso.usuarios, roles→acesso.perfis, etc.
from app.infrastructure.db.models.acesso import (
    Usuario as User,
    Perfil as Role,
    Permissao as Permission,
    UsuarioPerfil as UserRole,
    PerfilPermissao as RolePermission,
    RefreshToken,
)

__all__ = ["User", "Role", "Permission", "UserRole", "RolePermission", "RefreshToken"]
