import re

_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = (
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)
_MAX_LENGTH = 120

def safe_name(name, fallback="unnamed"):
    name = _INVALID.sub("_", (name or "").strip()).rstrip(". ")
    if not name:
        name = fallback
    if name.upper() in _RESERVED:
        name = "_" + name
    return name[:_MAX_LENGTH]

def unique_name(name, used, ext=""):
    candidate = name
    n = 2
    while (candidate + ext).lower() in used:
        candidate = f"{name}__{n}"
        n += 1
    used.add((candidate + ext).lower())
    return candidate + ext
