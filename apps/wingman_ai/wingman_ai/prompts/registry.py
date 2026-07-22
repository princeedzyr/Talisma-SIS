import json
from functools import lru_cache
from pathlib import Path


PROMPT_ROOT = Path(__file__).parent


@lru_cache(maxsize=64)
def get_prompt(name):
    prompt_path = PROMPT_ROOT / f"{name}.json"
    if not prompt_path.exists():
        raise KeyError(f"Unknown Wingman prompt: {name}")

    return json.loads(prompt_path.read_text(encoding="utf-8"))

