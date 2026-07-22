from dataclasses import dataclass

from wingman_ai.config.settings import get_bool_setting, get_dict_setting, get_setting


@dataclass(frozen=True)
class ERPServiceConfig:
    default_page_size: int = 20
    max_page_size: int = 100
    operation_timeout_seconds: int = 30
    cache_enabled: bool = True
    debug_mode: bool = False
    feature_flags: dict = None


def get_erp_service_config():
    return ERPServiceConfig(
        default_page_size=int(get_setting("wingman_erp_service_default_page_size", 20)),
        max_page_size=int(get_setting("wingman_erp_service_max_page_size", 100)),
        operation_timeout_seconds=int(get_setting("wingman_erp_service_timeout_seconds", 30)),
        cache_enabled=get_bool_setting("wingman_erp_service_cache_enabled", True),
        debug_mode=get_bool_setting("wingman_erp_service_debug_mode", False),
        feature_flags=get_dict_setting(
            "wingman_erp_service_feature_flags",
            {
                "document_operations": True,
                "search": True,
                "workflow": True,
                "validation": True,
                "permissions": True,
            },
        ),
    )


def clamp_page_size(page_size, config):
    try:
        requested = int(page_size or config.default_page_size)
    except (TypeError, ValueError):
        requested = config.default_page_size
    return max(1, min(requested, config.max_page_size))


def normalize_page(page):
    try:
        return max(1, int(page or 1))
    except (TypeError, ValueError):
        return 1
