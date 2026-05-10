"""GovGuard™ — Domain Exception Hierarchy"""


class GovGuardException(Exception):
    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    message: str = "An error occurred"
    details: dict = {}

    def __init__(self, message: str | None = None, details: dict | None = None):
        self.message = message or self.__class__.message
        self.details = details or {}
        super().__init__(self.message)


class AuthenticationError(GovGuardException):
    status_code = 401
    error_code = "AUTHENTICATION_FAILED"
    message = "Authentication failed"


class AuthorizationError(GovGuardException):
    status_code = 403
    error_code = "AUTHORIZATION_FAILED"
    message = "Insufficient permissions"


class NotFoundError(GovGuardException):
    status_code = 404
    error_code = "NOT_FOUND"
    message = "Resource not found"


class ConflictError(GovGuardException):
    status_code = 409
    error_code = "CONFLICT"
    message = "Resource already exists"


class ValidationError(GovGuardException):
    status_code = 422
    error_code = "VALIDATION_ERROR"
    message = "Validation failed"


class RateLimitError(GovGuardException):
    status_code = 429
    error_code = "RATE_LIMIT_EXCEEDED"
    message = "Rate limit exceeded. Retry after 60 seconds."


# Domain-specific
class GrantNotFound(NotFoundError):
    error_code = "GRANT_NOT_FOUND"
    message = "Grant not found"


class GrantAlreadyActive(ConflictError):
    error_code = "GRANT_ALREADY_ACTIVE"
    message = "Grant is already active and cannot be modified"


class TransactionNotFound(NotFoundError):
    error_code = "TRANSACTION_NOT_FOUND"
    message = "Transaction not found"


class TenantNotFound(NotFoundError):
    error_code = "TENANT_NOT_FOUND"
    message = "Tenant not found"


class UserNotFound(NotFoundError):
    error_code = "USER_NOT_FOUND"
    message = "User not found"


class ComplianceControlNotFound(NotFoundError):
    error_code = "CONTROL_NOT_FOUND"
    message = "Compliance control not found"


class FileTooLarge(GovGuardException):
    status_code = 413
    error_code = "FILE_TOO_LARGE"
    message = "File exceeds the 50MB size limit"


class ExternalAPIError(GovGuardException):
    status_code = 502
    error_code = "EXTERNAL_API_ERROR"
    message = "External API call failed"
