"""GATT Characteristic."""

from typing import Callable, Optional
from .utils import validate_uuid, validate_permissions


class Characteristic:
    """
    Represents a GATT Characteristic.

    Args:
        uuid: 128-bit or 16-bit UUID string.
        permissions: List: "read", "write", "write-without-response", "notify", "indicate".
        value: Initial value as bytes.
        on_read: Callback when a client reads. Signature: () -> bytes
        on_write: Callback when a client writes. Signature: (value: bytes) -> None
        description: Optional human-readable description.
    """

    def __init__(
        self,
        uuid: str,
        permissions: list,
        value: bytes = b"",
        on_read: Optional[Callable[[], bytes]] = None,
        on_write: Optional[Callable[[bytes], None]] = None,
        description: str = "",
    ):
        self.uuid = validate_uuid(uuid)
        self.permissions = validate_permissions(permissions)
        self._value = bytearray(value)
        self.on_read = on_read
        self.on_write = on_write
        self.description = description
        self._server = None  # Back-reference, set by GATTServer

    @property
    def value(self) -> bytes:
        return bytes(self._value)

    @value.setter
    def value(self, new_value: bytes) -> None:
        self._value = bytearray(new_value)
        if self._server and self._server.is_running:
            if "notify" in self.permissions or "indicate" in self.permissions:
                self._server._update_value(self.uuid, self._value)

    def handle_read(self) -> bytes:
        if self.on_read is not None:
            result = self.on_read()
            if isinstance(result, str):
                return result.encode("utf-8")
            return bytes(result)
        return self.value

    def handle_write(self, value: bytes) -> None:
        self._value = bytearray(value)
        if self.on_write is not None:
            self.on_write(bytes(value))

    async def notify(self, value: Optional[bytes] = None) -> None:
        if value is not None:
            self._value = bytearray(value)
        if self._server and self._server.is_running:
            self._server._update_value(self.uuid, self._value)

    def __repr__(self) -> str:
        return (
            "Characteristic(uuid=" + repr(self.uuid)
            + ", permissions=" + repr(self.permissions) + ")"
        )
