from wingman_ai.exception_intelligence import get_exception_interceptor


def guarded_api_call(operation, fn, **context):
    try:
        response = fn()
    except Exception as exc:
        return get_exception_interceptor().failure_response(
            exc,
            context={**context, "operation": operation, "failure_stage": context.get("failure_stage") or "API execution"},
        )
    return get_exception_interceptor().attach_to_response(
        response,
        context={**context, "operation": operation, "failure_stage": context.get("failure_stage") or "API response"},
    )
