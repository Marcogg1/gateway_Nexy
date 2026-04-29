"""GATT Service."""

from typing import Optional
from .characteristic import Characteristic
from .utils import validate_uuid


class Service:
    """
    Represents a GATT Service.

    Args:
        uuid: 128-bit or 16-bit UUID string.
        primary: Whether this is a primary service (almost always True).
    """

    def __init__(self, uuid: str, primary: bool = True):
        self.uuid = validate_uuid(uuid)
        self.primary = primary
        self.characteristics: list[Characteristic] = []

    def add_characteristic(self, characteristic: Characteristic) -> None:
        characteristic._service = self
        self.characteristics.append(characteristic)

    def get_characteristic_by_uuid(self, uuid: str) -> Optional[Characteristic]:
        normalized = validate_uuid(uuid)
        for char in self.characteristics:
            if char.uuid == normalized:
                return char
        return None

    def __repr__(self) -> str:
        return (
            "Service(uuid=" + repr(self.uuid)
            + ", chars=" + str(len(self.characteristics)) + ")"
        )
