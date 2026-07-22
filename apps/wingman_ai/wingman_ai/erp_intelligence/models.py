from dataclasses import asdict, is_dataclass
import re


def read_attr(value, key, default=None):
    if value is None:
        return default
    if isinstance(value, dict):
        return value.get(key, default)
    if hasattr(value, "get"):
        try:
            return value.get(key, default)
        except TypeError:
            pass
    return getattr(value, key, default)


def read_bool(value, key, default=False):
    item = read_attr(value, key, default)
    if isinstance(item, bool):
        return item
    if item in (None, ""):
        return default
    return bool(int(item)) if str(item).isdigit() else str(item).lower() in ("true", "yes", "on")


def split_csv(value):
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in re.split(r"[,\n]+", str(value)) if item.strip()]


def unique(values):
    seen = set()
    result = []
    for value in values:
        if value in (None, "") or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def to_plain(value):
    if is_dataclass(value):
        return {key: to_plain(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {key: to_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain(item) for item in value]
    return value
