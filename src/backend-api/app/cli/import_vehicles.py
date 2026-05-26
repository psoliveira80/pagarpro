"""CLI command: Import vehicles from Excel file.

Usage: python -m app.cli.import_vehicles path/to/file.xlsx [--dry-run]
"""

import argparse
import asyncio
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from app.infrastructure.db.session import get_sessionmaker
from app.infrastructure.db.models.asset import Asset
from app.modules.vehicles.models import Vehicle
from app.modules.vehicles.schemas import validate_plate
from app.application.shared.audit_logger import AuditLogger


# Column mapping: Excel header (PT-BR) -> model field
COLUMN_MAP: dict[str, str] = {
    "placa": "plate",
    "marca": "brand",
    "modelo": "model_name",
    "ano_modelo": "model_year",
    "ano_fabricacao": "fab_year",
    "ano_fab": "fab_year",
    "cor": "color",
    "chassi": "chassi",
    "renavam": "renavam",
    "codigo_fipe": "fipe_code",
    "valor_fipe": "fipe_value",
    "status": "status",
    "cliente_id": "customer_id",
    "tracker_id": "tracker_id",
}


def _normalize_header(header: str) -> str:
    """Normalize Excel header to snake_case key."""
    return header.strip().lower().replace(" ", "_").replace("-", "_")


async def import_vehicles(file_path: str, dry_run: bool = False) -> None:
    try:
        import openpyxl
    except ImportError:
        print("ERROR: openpyxl is required. Install with: pip install openpyxl")
        sys.exit(1)

    path = Path(file_path)
    if not path.exists():
        print(f"ERROR: File not found: {file_path}")
        sys.exit(1)

    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.active
    if ws is None:
        print("ERROR: No active worksheet found")
        sys.exit(1)

    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        print("ERROR: File has no data rows (only header or empty)")
        sys.exit(1)

    # Map headers
    raw_headers = [str(h or "").strip() for h in rows[0]]
    headers: list[str] = []
    for h in raw_headers:
        norm = _normalize_header(h)
        mapped = COLUMN_MAP.get(norm, norm)
        headers.append(mapped)

    if "plate" not in headers:
        print(f"ERROR: 'placa' (plate) column is required. Found headers: {raw_headers}")
        sys.exit(1)

    data_rows = rows[1:]
    print(f"Found {len(data_rows)} data rows in {path.name}")

    created = 0
    skipped = 0
    errors = 0

    session_factory = get_sessionmaker()
    async with session_factory() as session:
        async with session.begin():
            for row_idx, row in enumerate(data_rows, start=2):
                record = dict(zip(headers, row))

                plate_raw = record.get("plate")
                if not plate_raw:
                    print(f"  Row {row_idx}: SKIP — no plate value")
                    skipped += 1
                    continue

                try:
                    plate = validate_plate(str(plate_raw))
                except ValueError as e:
                    print(f"  Row {row_idx}: ERROR — {e}")
                    errors += 1
                    continue

                # Idempotent by plate
                existing = await session.execute(
                    select(Vehicle).where(Vehicle.plate == plate)
                )
                if existing.scalar_one_or_none():
                    print(f"  Row {row_idx}: SKIP — plate {plate} already exists")
                    skipped += 1
                    continue

                brand = str(record.get("brand", "")).strip()
                model_name = str(record.get("model_name", "")).strip()

                if not brand or not model_name:
                    print(f"  Row {row_idx}: ERROR — brand and model_name are required")
                    errors += 1
                    continue

                model_year = int(record.get("model_year", 0) or 0)
                fab_year = int(record.get("fab_year", 0) or 0)
                if model_year == 0 or fab_year == 0:
                    print(f"  Row {row_idx}: ERROR — model_year and fab_year are required")
                    errors += 1
                    continue

                if dry_run:
                    print(f"  Row {row_idx}: DRY-RUN — would create {plate} ({brand} {model_name})")
                    created += 1
                    continue

                # Create Asset
                asset = Asset(
                    module_id="vehicle",
                    external_ref=plate,
                    display_name=f"{brand} {model_name} ({plate})",
                    status=str(record.get("status", "disponivel") or "disponivel"),
                )
                session.add(asset)
                await session.flush()

                # Build vehicle
                customer_id_raw = record.get("customer_id")
                customer_id = UUID(str(customer_id_raw)) if customer_id_raw else None

                fipe_value = record.get("fipe_value")

                vehicle = Vehicle(
                    plate=plate,
                    brand=brand,
                    model_name=model_name,
                    model_year=model_year,
                    fab_year=fab_year,
                    color=str(record.get("color", "") or "").strip() or None,
                    chassi=str(record.get("chassi", "") or "").strip() or None,
                    renavam=str(record.get("renavam", "") or "").strip() or None,
                    fipe_code=str(record.get("fipe_code", "") or "").strip() or None,
                    fipe_value=fipe_value if fipe_value else None,
                    status=str(record.get("status", "disponivel") or "disponivel"),
                    customer_id=customer_id,
                    asset_id=asset.id,
                    tracker_id=str(record.get("tracker_id", "") or "").strip() or None,
                )
                session.add(vehicle)
                created += 1
                print(f"  Row {row_idx}: CREATED — {plate} ({brand} {model_name})")

            if not dry_run and created > 0:
                # Audit log
                audit = AuditLogger(session)
                await audit.record(
                    action="vehicles.bulk_import",
                    entity="vehicle",
                    payload_after={
                        "file": path.name,
                        "created": created,
                        "skipped": skipped,
                        "errors": errors,
                    },
                    module="vehicles",
                    category="data",
                    severity="info",
                )

    print(f"\nImport complete: {created} created, {skipped} skipped, {errors} errors")
    if dry_run:
        print("(DRY-RUN mode — no changes were committed)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import vehicles from Excel")
    parser.add_argument("file", help="Path to the .xlsx file")
    parser.add_argument("--dry-run", action="store_true", help="Preview without committing")
    args = parser.parse_args()

    asyncio.run(import_vehicles(args.file, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
