# Backward-compat shim — story 12.3 will update all direct imports.
# module_hooks_config renamed to config.politicas_eventos_modulo in migration 0015.
from app.infrastructure.db.models.config import PoliticaEventoModulo as ModuleHooksConfig

__all__ = ["ModuleHooksConfig"]
