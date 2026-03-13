class AppError(Exception):
    status_code = 400
    detail = "Application error"


class NotFoundError(AppError):
    status_code = 404
    detail = "Resource not found"


class ConflictError(AppError):
    status_code = 409
    detail = "Conflict"


class ValidationError(AppError):
    status_code = 422
    detail = "Validation failed"


class ForbiddenError(AppError):
    status_code = 403
    detail = "Forbidden"
