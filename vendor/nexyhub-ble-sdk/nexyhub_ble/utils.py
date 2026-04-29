"""Utility functions for nexyhub_ble."""

import re
from .exceptions import InvalidUUIDError

BT_BASE_UUID_SUFFIX = "-0000-1000-8000-00805f9b34fb"
UUID_128_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
UUID_16_RE = re.compile(r"^(0x)?[0-9a-f]{4}$", re.IGNORECASE)


def validate_uuid(uuid: str) -> str:
    uuid = uuid.strip()
    if UUID_128_RE.match(uuid):
        return uuid.lower()
    if UUID_16_RE.match(uuid):
        short = uuid.lower().replace("0x", "")
        return ("0000" + short + BT_BASE_UUID_SUFFIX).lower()
    raise InvalidUUIDError(
        "UUID must be 128-bit or 16-bit. Got: " + repr(uuid)
    )


def validate_permissions(permissions: list) -> list:
    valid = {"read", "write", "write-without-response", "notify", "indicate"}
    perms = [p.lower().strip() for p in permissions]
    for p in perms:
        if p not in valid:
            raise ValueError("Invalid permission: " + repr(p))
    return perms
