"""Pure assertion helpers for the EG-64 compressed DDM response envelope.

No Azure here — keeps the test groups free of envelope-shape duplication.
Contract: src/cloudApi/method_request_handler.py (EG-64 design spec §3).
"""

from typing import Any


def is_envelope(resp: Any) -> bool:
    """True if resp looks like a compressed envelope (has an int ``ts``)."""
    return isinstance(resp, dict) and isinstance(resp.get("ts"), int)


def items(resp: dict) -> list[dict]:
    """The ``d`` item array of a param-DDM envelope ([] if absent)."""
    d = resp.get("d", [])
    return d if isinstance(d, list) else []


def item_ok(item: dict) -> bool:
    """A success item carries no ``ec``."""
    return "ec" not in item


def resp_ok(resp: dict) -> bool:
    """Whole-envelope success: no ``es`` and every item ok."""
    return "es" not in resp and all(item_ok(i) for i in items(resp))


def error_of(resp: Any) -> str:
    """Human summary of envelope/item errors ('' if clean)."""
    if not isinstance(resp, dict):
        return repr(resp)[:80]
    parts = []
    if "es" in resp:
        parts.append(f"es={resp['es']}")
    if "ec" in resp:
        parts.append(f"ec={resp['ec']}")
    for i in items(resp):
        if "ec" in i:
            parts.append(f"p={i.get('p')}:ec={i['ec']}")
    return " ".join(parts)


def value_of(resp: dict, pid: str) -> str | None:
    """The ``v`` of the item whose ``p`` == pid (None if absent)."""
    return next((i.get("v") for i in items(resp) if i.get("p") == pid), None)


def is_placeholder(resp: Any) -> bool:
    """True for a not-yet-implemented DDM body: {'result': True, 'message': str}."""
    return (isinstance(resp, dict) and resp.get("result") is True
            and isinstance(resp.get("message"), str))
