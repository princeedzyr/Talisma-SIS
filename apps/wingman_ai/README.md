# Talisma Wingman AI

Talisma Wingman AI is the AI assistant for Talisma OneCampus.

This app is intentionally isolated from Talisma OneCampus core. It should be installed as a normal Frappe app and loaded through hooks.

## Current Status

The app skeleton, Desk chat shell, backend chat endpoint, and first enterprise backend layers are in place.

Added:

- Floating Wingman button on Desk pages through `hooks.py`
- Chat panel shell
- Responsive and dark-mode-aware CSS
- Keyboard shortcut: `Ctrl+Shift+W`
- Frappe whitelisted backend endpoint: `wingman_ai.api.chat.send`
- Basic Talisma OneCampus Desk context awareness from the current route
- Application orchestrator
- Intent router
- Capability router
- Initial CRM, sales, workflow, email, reports, navigation, and reasoning capabilities
- Talisma OneCampus metadata and permission integration helpers
- AI provider configuration detection
- Ollama provider integration using `phi3:latest` by default
- Compatibility endpoints for legacy migration
- Prompt-based Desk navigation, for example `open CRM`, `open Stock`, `open customer list`, `open user Administrator`, and `open sales order SAL-ORD-2026-00001`
- Permission-aware Talisma OneCampus navigation lookup through the Talisma OneCampus integration layer
- Formal conversation, planner, execution, security, configuration, and logging foundations
- Reusable AI Core with provider abstraction, Ollama provider, prompt manager, session recovery, and conversation APIs

General, reasoning, and report-planning responses can use Ollama when the Talisma OneCampus container can reach it. Write actions are intentionally routed into review-required responses first.

## Ollama Configuration

For Docker Desktop on Windows, Ollama usually runs on the host machine and Talisma OneCampus can reach it through:

```text
http://host.docker.internal:11434
```

The default model is:

```text
phi3:latest
```

Recommended site config:

```bash
bench --site frontend set-config wingman_ai_provider ollama
bench --site frontend set-config ollama_base_url http://host.docker.internal:11434
bench --site frontend set-config ollama_model phi3:latest
```

## Planned Structure

```text
wingman_ai/
  wingman_ai/
    api/
    application/
    capabilities/
    integrations/
    repositories/
    services/
    public/
      js/
      css/
    hooks.py
  deployment/
```
