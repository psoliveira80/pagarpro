# Backward-compat shim — story 12.3 will update all direct imports.
# SystemSetting (key/value TEXT PK) was replaced by ConfiguracaoSistema (UUID PK + empresa_id).
from app.infrastructure.db.models.config import ConfiguracaoSistema as SystemSetting

__all__ = ["SystemSetting"]
