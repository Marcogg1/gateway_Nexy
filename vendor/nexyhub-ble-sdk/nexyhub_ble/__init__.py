"""
nexyhub_ble — BLE GATT Server framework for NexyHub.

Built on top of 'bless' for reliable BlueZ communication.

Quick start:
    from nexyhub_ble import GATTServer, Service, Characteristic

    server = GATTServer(name="MyDevice")
    svc = Service(uuid="de0a7b0c-358f-4cef-b778-000000000000")
    svc.add_characteristic(Characteristic(
        uuid="de0a7b0c-358f-4cef-b778-000000000002",
        permissions=["read", "notify"],
        on_read=lambda: b"hello",
    ))
    server.add_service(svc)
    asyncio.run(server.run_forever())
"""

__version__ = "0.7.0"

from .server import GATTServer
from .service import Service
from .characteristic import Characteristic
from .exceptions import (
    NexyHubBLEError,
    AdapterNotFoundError,
    ServerAlreadyRunningError,
    ServerNotRunningError,
    ServiceRegistrationError,
    AdvertisementError,
    InvalidUUIDError,
    CharacteristicError,
)

__all__ = [
    "GATTServer",
    "Service",
    "Characteristic",
    "NexyHubBLEError",
    "AdapterNotFoundError",
    "ServerAlreadyRunningError",
    "ServerNotRunningError",
    "ServiceRegistrationError",
    "AdvertisementError",
    "InvalidUUIDError",
    "CharacteristicError",
]
