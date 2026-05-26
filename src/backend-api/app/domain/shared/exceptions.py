class DomainError(Exception):
    code: str = "DOMAIN_ERROR"
    http_status: int = 400


class NotFoundError(DomainError):
    code = "NOT_FOUND"
    http_status = 404


class RuleViolation(DomainError):
    code = "RULE_VIOLATION"
    http_status = 409
