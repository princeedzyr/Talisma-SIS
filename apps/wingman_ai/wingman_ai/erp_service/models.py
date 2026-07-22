from dataclasses import dataclass, field
from time import perf_counter
from uuid import uuid4


@dataclass(frozen=True)
class ServiceError:
    code: str
    message: str
    fieldname: str = None

    def to_dict(self):
        return {
            "code": self.code,
            "message": self.message,
            "fieldname": self.fieldname,
        }


@dataclass(frozen=True)
class ValidationIssue:
    fieldname: str
    message: str
    issue_type: str = "validation"
    severity: str = "error"

    def to_dict(self):
        return {
            "fieldname": self.fieldname,
            "message": self.message,
            "issue_type": self.issue_type,
            "severity": self.severity,
        }


@dataclass
class ServiceResponse:
    success: bool
    result: object = None
    warnings: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    validation_issues: list = field(default_factory=list)
    execution_time_ms: float = 0.0
    trace_id: str = None

    def to_dict(self):
        return {
            "success": self.success,
            "result": to_plain(self.result),
            "warnings": list(self.warnings or []),
            "errors": [to_plain(error) for error in self.errors or []],
            "validation_issues": [to_plain(issue) for issue in self.validation_issues or []],
            "execution_time_ms": self.execution_time_ms,
            "trace_id": self.trace_id,
        }


class ResponseBuilder:
    def __init__(self):
        self.trace_id = uuid4().hex
        self.started_at = perf_counter()

    def success(self, result=None, warnings=None, validation_issues=None):
        return ServiceResponse(
            success=True,
            result=result,
            warnings=warnings or [],
            validation_issues=validation_issues or [],
            execution_time_ms=self.elapsed_ms(),
            trace_id=self.trace_id,
        )

    def failure(self, code, message, validation_issues=None, fieldname=None, warnings=None):
        return ServiceResponse(
            success=False,
            warnings=warnings or [],
            errors=[ServiceError(code=code, message=message, fieldname=fieldname)],
            validation_issues=validation_issues or [],
            execution_time_ms=self.elapsed_ms(),
            trace_id=self.trace_id,
        )

    def exception(self, exc):
        return self.failure(code="unexpected_error", message=safe_exception_message(exc))

    def elapsed_ms(self):
        return round((perf_counter() - self.started_at) * 1000, 2)


def to_plain(value):
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return value.to_dict()
    if isinstance(value, dict):
        return {key: to_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain(item) for item in value]
    return value


def safe_exception_message(exc):
    return "The operation could not be completed safely."
