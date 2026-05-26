from contextvars import ContextVar
from uuid import uuid4

correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="")


def generate_correlation_id() -> str:
    cid = str(uuid4())
    correlation_id_ctx.set(cid)
    return cid


def get_correlation_id() -> str:
    return correlation_id_ctx.get()
