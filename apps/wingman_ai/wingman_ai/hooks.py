app_name = "wingman_ai"
app_title = "Talisma Wingman AI"
app_publisher = "Talisma"
app_description = "AI work partner for Talisma OneCampus"
app_email = "support@example.com"
app_license = "MIT"

# Talisma SIS owns the application shell and education model. Wingman only
# contributes the floating assistant layer and metadata-aware backend.
required_apps = ["erpnext", "education", "talisma_sis"]
app_include_js = ["/assets/wingman_ai/js/wingman_chat.js?v=20260722.25"]
app_include_css = ["/assets/wingman_ai/css/wingman_chat.css?v=20260722.21"]

after_migrate = "wingman_ai.erp_intelligence.cache.refresh_metadata_cache"
scheduler_events = {
    "hourly": ["wingman_ai.erp_intelligence.cache.refresh_metadata_cache"],
}
