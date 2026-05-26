# Backward-compat shim — story 12.3 will update all direct imports.
# Vehicle models moved to app.infrastructure.db.models.veiculos in migration 0015.
from app.infrastructure.db.models.veiculos import (
    Veiculo as Vehicle,
    AquisicaoVeiculo as VehicleAcquisition,
    DispositivoRastreamento as TrackerDevice,
)

__all__ = ["Vehicle", "VehicleAcquisition", "TrackerDevice"]
