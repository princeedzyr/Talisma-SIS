def log_event(event_type, payload=None, user=None):
    return {
        "logged": False,
        "event_type": event_type,
        "user": user,
        "payload": payload or {},
        "reason": "Audit DocType has not been installed yet.",
    }

