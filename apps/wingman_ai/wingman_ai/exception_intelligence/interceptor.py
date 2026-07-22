from datetime import datetime

from wingman_ai.exception_intelligence.classifier import ExceptionClassifier
from wingman_ai.exception_intelligence.recovery import RecoveryPlanner
from wingman_ai.exception_intelligence.renderer import DiagnosticRenderer
from wingman_ai.exception_intelligence.retry import RetryManager
from wingman_ai.exception_intelligence.operations_center import get_operations_center
from wingman_ai.exception_intelligence.root_cause import RootCauseAnalyzer
from wingman_ai.exception_intelligence.session import SessionPreservationService
from wingman_ai.logging.service import log_error, log_warning


class ExceptionInterceptor:
    def __init__(self, classifier=None, analyzer=None, recovery=None, session=None, renderer=None, retry=None, operations_center=None):
        self.classifier = classifier or ExceptionClassifier()
        self.analyzer = analyzer or RootCauseAnalyzer()
        self.recovery = recovery or RecoveryPlanner()
        self.session = session or SessionPreservationService()
        self.renderer = renderer or DiagnosticRenderer()
        self.retry = retry or RetryManager()
        self.operations_center = operations_center or get_operations_center()

    def from_exception(self, exc, context=None):
        context = dict(context or {})
        preserved = self.session.preserve(context)
        classification = self.classifier.classify(exc=exc, context=context)
        analysis = self.analyzer.analyze(classification, exc=exc, context=context)
        recovery = self.recovery.plan(classification, analysis, preserved_session=preserved)
        retry_state = self.retry.build_retry_state(recovery, preserved_session=preserved)
        diagnostic = self.prepare_operations_center_diagnostic(analysis, recovery, retry_state, preserved)
        recovery = {**recovery, "actions": diagnostic.get("actions") or []}
        message = self.renderer.render(analysis, recovery, retry_state)
        self.log(diagnostic, context=context, exc=exc)
        return {"message": message, "diagnostic": diagnostic}

    def from_response(self, response, context=None):
        context = dict(context or {})
        preserved = self.session.preserve(context)
        classification = self.classifier.classify(response=response, context=context)
        analysis = self.analyzer.analyze(classification, response=response, context=context)
        recovery = self.recovery.plan(classification, analysis, preserved_session=preserved)
        retry_state = self.retry.build_retry_state(recovery, preserved_session=preserved)
        diagnostic = self.prepare_operations_center_diagnostic(analysis, recovery, retry_state, preserved)
        recovery = {**recovery, "actions": diagnostic.get("actions") or []}
        message = self.renderer.render(analysis, recovery, retry_state)
        self.log(diagnostic, context=context)
        return {"message": message, "diagnostic": diagnostic}

    def prepare_operations_center_diagnostic(self, analysis, recovery, retry_state, preserved):
        diagnostic = self.renderer.diagnostic(analysis, recovery, retry_state)
        diagnostic["preserved_session"] = preserved
        diagnostic["timestamp"] = datetime.utcnow().isoformat()
        diagnostic = self.operations_center.register_diagnostic(diagnostic)
        diagnostic["actions"] = self.operations_center.build_actions(diagnostic, retry_state=retry_state)
        diagnostic["recovery_options"] = [action.get("label") for action in diagnostic["actions"] if action.get("label")]
        return self.operations_center.register_diagnostic(diagnostic)

    def attach_to_response(self, response, context=None):
        if not isinstance(response, dict) or response.get("success") is True:
            return response
        if has_interactive_recovery(response):
            return response
        if response.get("exception_diagnostic"):
            diagnostic = response.get("exception_diagnostic") or {}
            if diagnostic.get("actions") and not response.get("actions"):
                response["actions"] = diagnostic.get("actions")
            return response
        diagnostic = self.from_response(
            response,
            context={
                **dict(context or {}),
                "validation_issues": response.get("validation_issues") or [],
            },
        )
        response["exception_diagnostic"] = diagnostic["diagnostic"]
        response["actions"] = diagnostic["diagnostic"].get("actions") or []
        response.setdefault("message", diagnostic["message"])
        return response

    def failure_response(self, exc, context=None):
        diagnostic = self.from_exception(exc, context=context)
        return {
            "success": False,
            "status": "error",
            "message": diagnostic["message"],
            "errors": [
                {
                    "code": "wingman_exception_diagnostic",
                    "message": "Wingman prepared a diagnostic for this failure.",
                }
            ],
            "validation_issues": [],
            "exception_diagnostic": diagnostic["diagnostic"],
            "actions": diagnostic["diagnostic"].get("actions") or [],
        }

    def log(self, diagnostic, context=None, exc=None):
        payload = {
            "timestamp": diagnostic.get("timestamp"),
            "operation": diagnostic.get("operation"),
            "doctype": (diagnostic.get("preserved_session") or {}).get("doctype"),
            "conversation_id": (diagnostic.get("preserved_session") or {}).get("conversation_id"),
            "diagnostic_id": diagnostic.get("diagnostic_id"),
            "exception_category": diagnostic.get("category"),
            "root_cause": diagnostic.get("root_cause"),
            "recovery_strategy": diagnostic.get("recovery_strategy"),
            "resolution_status": "open",
            "retry_count": ((diagnostic.get("retry") or {}).get("retry_count")),
            "framework_component": diagnostic.get("framework_component"),
        }
        if exc:
            log_error("Wingman exception intercepted", error_type=type(exc).__name__, **payload)
        else:
            log_warning("Wingman failure diagnostic prepared", **payload)


_INTERCEPTOR = None


def get_exception_interceptor():
    global _INTERCEPTOR
    if _INTERCEPTOR is None:
        _INTERCEPTOR = ExceptionInterceptor()
    return _INTERCEPTOR


def has_interactive_recovery(response):
    follow_up = response.get("follow_up") if isinstance(response, dict) else None
    if not isinstance(follow_up, dict):
        return False
    actions = follow_up.get("actions")
    message = follow_up.get("message")
    return bool(message or actions)
