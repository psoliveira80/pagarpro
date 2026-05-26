"""Global unified search endpoint for command palette (Story 9-11)."""

import structlog
from fastapi import APIRouter, Query
from sqlalchemy import text, union_all, literal_column, select

from app.api.deps import CurrentUserDep, SessionDep
from app.api.v1.schemas.admin import GlobalSearchResponse, SearchResultItem

log = structlog.get_logger()

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/global", response_model=GlobalSearchResponse)
async def global_search(
    q: str = Query(..., min_length=1, max_length=200),
    type: str | None = Query(None, description="Filter by type: customer, vehicle, contract"),
    session: SessionDep = ...,  # type: ignore[assignment]
    current_user: CurrentUserDep = ...,  # type: ignore[assignment]
) -> GlobalSearchResponse:
    """Search across customers, vehicles (assets), and contracts."""
    search_term = q.strip()
    like_term = f"%{search_term}%"
    limit = 20

    results: list[SearchResultItem] = []

    # Build queries per type
    if type is None or type == "customer":
        customer_q = text(
            """
            SELECT id::text, 'customer' as type, nome_completo as title,
                   cpf_cnpj as subtitle
            FROM cadastro.clientes
            WHERE excluido_em IS NULL
              AND (
                unaccent(nome_completo) ILIKE unaccent(:like_term)
                OR cpf_cnpj ILIKE :like_term
                OR email ILIKE :like_term
                OR telefone ILIKE :like_term
              )
            LIMIT :lim
            """
        )
        rows = (await session.execute(customer_q, {"like_term": like_term, "lim": limit})).fetchall()
        for r in rows:
            results.append(SearchResultItem(
                id=r[0], type=r[1], title=r[2], subtitle=r[3],
                url=f"/system/customers/{r[0]}",
            ))

    if type is None or type == "vehicle":
        vehicle_q = text(
            """
            SELECT v.id::text, 'vehicle' as type,
                   (v.fipe_marca || ' ' || v.fipe_modelo || ' (' || v.placa || ')') as title,
                   v.placa as subtitle
            FROM veiculos.veiculos v
            WHERE v.excluido_em IS NULL
              AND (
                unaccent(v.fipe_marca || ' ' || v.fipe_modelo) ILIKE unaccent(:like_term)
                OR v.placa ILIKE :like_term
              )
            LIMIT :lim
            """
        )
        rows = (await session.execute(vehicle_q, {"like_term": like_term, "lim": limit})).fetchall()
        for r in rows:
            results.append(SearchResultItem(
                id=r[0], type=r[1], title=r[2], subtitle=r[3],
                url=f"/system/vehicles",
            ))

    if type is None or type == "contract":
        contract_q = text(
            """
            SELECT c.id::text, 'contract' as type, c.numero as title,
                   cu.nome_completo as subtitle
            FROM contrato.contratos c
            LEFT JOIN cadastro.clientes cu ON cu.id = c.cliente_id
            WHERE c.excluido_em IS NULL
              AND (
                c.numero ILIKE :like_term
                OR unaccent(cu.nome_completo) ILIKE unaccent(:like_term)
              )
            LIMIT :lim
            """
        )
        rows = (await session.execute(contract_q, {"like_term": like_term, "lim": limit})).fetchall()
        for r in rows:
            results.append(SearchResultItem(
                id=r[0], type=r[1], title=r[2], subtitle=r[3],
                url=f"/system/contracts/{r[0]}",
            ))

    return GlobalSearchResponse(results=results, total=len(results))
