"""
GATTServer — Main entry point for nexyhub_ble.

Built on top of the 'bless' library which handles all
BlueZ/D-Bus communication internally.
"""

import asyncio
import signal
import logging
from typing import Optional, Callable

from bless import (
    BlessServer,
    BlessGATTCharacteristic,
    GATTCharacteristicProperties,
    GATTAttributePermissions,
)

from .service import Service
from .characteristic import Characteristic
from .exceptions import ServerAlreadyRunningError, ServerNotRunningError

logger = logging.getLogger("nexyhub_ble")

# Map our permission strings to bless flags
_PROP_MAP = {
    "read": GATTCharacteristicProperties.read,
    "write": GATTCharacteristicProperties.write,
    "write-without-response": GATTCharacteristicProperties.write_without_response,
    "notify": GATTCharacteristicProperties.notify,
    "indicate": GATTCharacteristicProperties.indicate,
}

_PERM_READ = GATTAttributePermissions.readable
_PERM_WRITE = GATTAttributePermissions.writeable


class GATTServer:
    """
    BLE GATT Server.

    Example:
        server = GATTServer(name="NexyHub-GW")
        wifi = Service(uuid="de0a7b0c-358f-4cef-b778-000000000000")
        wifi.add_characteristic(Characteristic(
            uuid="de0a7b0c-358f-4cef-b778-000000000002",
            permissions=["write"],
            on_write=handle_start_scan,
        ))
        server.add_service(wifi)
        asyncio.run(server.run_forever())
    """

    def __init__(self, adapter: str = "hci0", name: str = "NexyHub"):
        self.adapter = adapter
        self.name = name
        self._services: list[Service] = []
        self._bless: Optional[BlessServer] = None
        self._running = False
        self._char_map: dict[str, Characteristic] = {}  # uuid -> our Characteristic

        # Public callbacks
        self.on_connect: Optional[Callable[[str], None]] = None
        self.on_disconnect: Optional[Callable[[str], None]] = None

    def add_service(self, service: Service) -> None:
        self._services.append(service)
        logger.info(
            "Service added: " + service.uuid
            + " (" + str(len(service.characteristics)) + " characteristics)"
        )

    def get_service(self, uuid: str) -> Optional[Service]:
        from .utils import validate_uuid
        normalized = validate_uuid(uuid)
        for svc in self._services:
            if svc.uuid == normalized:
                return svc
        return None

    def _on_read(self, characteristic: BlessGATTCharacteristic, **kwargs) -> bytearray:
        """Called by bless when a client reads a characteristic."""
        uuid = str(characteristic.uuid).lower()
        our_char = self._char_map.get(uuid)
        if our_char:
            value = our_char.handle_read()
            characteristic.value = bytearray(value)
            logger.debug("Read " + uuid + ": " + repr(value))
        return characteristic.value

    def _on_write(self, characteristic: BlessGATTCharacteristic, value: bytearray, **kwargs):
        """Called by bless when a client writes to a characteristic."""
        uuid = str(characteristic.uuid).lower()
        our_char = self._char_map.get(uuid)
        if our_char:
            logger.debug("Write " + uuid + ": " + repr(bytes(value)))
            our_char.handle_write(bytes(value))

    def _update_value(self, uuid: str, value: bytearray):
        """Update a characteristic value in bless (triggers notification)."""
        if self._bless:
            self._bless.get_characteristic(uuid).value = bytearray(value)
            self._bless.update_value(self._services[0].uuid, uuid)

    async def start(self) -> None:
        if self._running:
            raise ServerAlreadyRunningError("Server is already running")
        if not self._services:
            raise ValueError("No services added. Call add_service() first.")

        total_chars = sum(len(s.characteristics) for s in self._services)
        logger.info(
            "Starting GATT server '" + self.name + "' on " + self.adapter
            + " with " + str(len(self._services)) + " service(s), "
            + str(total_chars) + " characteristic(s)"
        )

        # Create bless server
        self._bless = BlessServer(name=self.name)
        self._bless.read_request_func = self._on_read
        self._bless.write_request_func = self._on_write

        # Register all services and characteristics
        for svc in self._services:
            await self._bless.add_new_service(svc.uuid)

            for char in svc.characteristics:
                # Build bless properties flags
                props = GATTCharacteristicProperties(0)
                for perm in char.permissions:
                    if perm in _PROP_MAP:
                        props = props | _PROP_MAP[perm]

                # Build bless attribute permissions
                attr_perms = GATTAttributePermissions(0)
                if "read" in char.permissions:
                    attr_perms = attr_perms | _PERM_READ
                if any(p in char.permissions for p in ("write", "write-without-response")):
                    attr_perms = attr_perms | _PERM_WRITE

                await self._bless.add_new_characteristic(
                    svc.uuid,
                    char.uuid,
                    props,
                    bytearray(char._value),
                    attr_perms,
                )

                # Register in our lookup map
                self._char_map[char.uuid] = char
                char._server = self

                logger.debug(
                    "  Registered char: " + char.uuid
                    + " " + repr(char.permissions)
                )

        # Start the server (registers with BlueZ + starts advertising)
        await self._bless.start()

        self._running = True
        logger.info("GATT server started successfully")

    async def stop(self) -> None:
        if not self._running:
            raise ServerNotRunningError("Server is not running")

        logger.info("Stopping GATT server...")
        if self._bless:
            await self._bless.stop()
            self._bless = None

        self._running = False
        logger.info("GATT server stopped")

    async def run_forever(self) -> None:
        await self.start()

        stop_event = asyncio.Event()

        def handle_signal():
            logger.info("Shutdown signal received")
            stop_event.set()

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, handle_signal)

        logger.info("Server running. Press Ctrl+C to stop.")

        try:
            await stop_event.wait()
        finally:
            await self.stop()

    @property
    def is_running(self) -> bool:
        return self._running

    def __repr__(self) -> str:
        status = "running" if self._running else "stopped"
        return (
            "GATTServer(name=" + repr(self.name)
            + ", status=" + status
            + ", services=" + str(len(self._services)) + ")"
        )
