from dataclasses import dataclass

from wingman_ai.config.settings import get_bool_setting, get_dict_setting, get_setting


@dataclass(frozen=True)
class ERPIntelligenceConfig:
    cache_ttl_seconds: int = 3600
    refresh_strategy: str = "lazy"
    discovery_mode: str = "standard"
    feature_flags: dict = None
    debug_mode: bool = False
    max_doctypes: int = 800
    max_fields_per_doctype: int = 500
    auto_refresh_enabled: bool = True
    startup_load_enabled: bool = False


def get_erp_intelligence_config():
    return ERPIntelligenceConfig(
        cache_ttl_seconds=int(get_setting("wingman_erp_metadata_cache_ttl", 3600)),
        refresh_strategy=str(get_setting("wingman_erp_metadata_refresh_strategy", "lazy")),
        discovery_mode=str(get_setting("wingman_erp_metadata_discovery_mode", "standard")),
        feature_flags=get_dict_setting(
            "wingman_erp_metadata_feature_flags",
            {
                "metadata_discovery": True,
                "relationship_discovery": True,
                "workflow_discovery": True,
                "permission_intelligence": True,
                "search_metadata": True,
            },
        ),
        debug_mode=get_bool_setting("wingman_erp_metadata_debug_mode", False),
        max_doctypes=int(get_setting("wingman_erp_metadata_max_doctypes", 800)),
        max_fields_per_doctype=int(get_setting("wingman_erp_metadata_max_fields_per_doctype", 500)),
        auto_refresh_enabled=get_bool_setting("wingman_erp_metadata_auto_refresh", True),
        startup_load_enabled=get_bool_setting("wingman_erp_metadata_startup_load", False),
    )
