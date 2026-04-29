"""Domain types and Status payload for the modern BLE WiFi protocol.

Status is the single source of truth pushed to the mobile app. It has two
serializations:

- `to_json()` — full Status, returned by the BLE READ on the Status char.
- `to_tick_json()` — small "tick" carrying only `seq`, `phase`,
  `last_updated_ms`, used as the NOTIFY payload (always fits any MTU).

See `docs/superpowers/specs/2026-04-23-eg58-ble-design.md` for the full
wire contract.
"""

import json
from dataclasses import asdict, dataclass, field
from enum import Enum, unique

# The BLE GATT spec caps a single characteristic value at 512 bytes. Budget:
#   - Status base fields (seq, phase, iface, current, error, last_updated_ms)
#     ~190 bytes worst case (32-char SSID in `current`, max IP, large seq+ts).
#   - Per network entry {"ssid":<32ch>,"rssi":-40,"security":"WPA2"} ~72 bytes.
#   - 4 entries × 72 + 3 separator commas + 2 brackets + 190 base ≈ 483 bytes.
# 4 guarantees the payload fits under 512 bytes for any SSID up to the 802.11
# 32-byte legal max. Mobile sees the strongest 4 networks; rescan to refresh.
MAX_NETWORKS_IN_STATUS = 4


@unique
class Phase(str, Enum):
    """Top-level WiFi subsystem state. Drives mobile UI."""

    IDLE = "idle"
    SCANNING = "scanning"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


@unique
class ErrorCode(str, Enum):
    """Typed error codes emitted in `Status.error.code`."""

    PSK_TOO_SHORT = "PSK_TOO_SHORT"
    PSK_WRONG = "PSK_WRONG"
    SSID_NOT_FOUND = "SSID_NOT_FOUND"
    TIMEOUT = "TIMEOUT"
    INVALID_REQUEST = "INVALID_REQUEST"


@dataclass(frozen=True)
class NetworkInfo:
    """One WiFi network observed during a scan."""

    ssid: str
    rssi: int
    security: str


@dataclass(frozen=True)
class ConnectionInfo:
    """Identifying info for the currently-connected WiFi network."""

    ssid: str
    rssi: int
    ip: str


@dataclass(frozen=True)
class StatusError:
    """Typed error attached to Status when phase == ERROR."""

    code: str
    message: str


@dataclass
class Status:
    """Complete WiFi subsystem snapshot.

    Two serializations:
      - to_json(): full state for the BLE READ.
      - to_tick_json(): small {seq, phase, last_updated_ms} for the NOTIFY.
    """

    seq: int = 0
    phase: Phase = Phase.IDLE
    iface: str | None = None
    current: ConnectionInfo | None = None
    networks: list[NetworkInfo] = field(default_factory=list)
    error: StatusError | None = None
    last_updated_ms: int = 0

    def to_json(self) -> bytes:
        """Compact full Status JSON for the BLE READ."""
        return json.dumps(asdict(self), separators=(",", ":")).encode()

    def to_tick_json(self) -> bytes:
        """Small NOTIFY payload — fits any MTU. Mobile reads full Status next."""
        return json.dumps(
            {
                "seq": self.seq,
                "phase": self.phase.value,
                "last_updated_ms": self.last_updated_ms,
            },
            separators=(",", ":"),
        ).encode()
