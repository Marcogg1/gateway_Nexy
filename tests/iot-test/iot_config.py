"""Harness config: targets, allowlists, safe params, test cases.

SAFETY: the harness refuses to run against any hub/device not listed here
(override only with --unsafe-target). Fill TEST_HUB_ALLOWLIST with the test
hub name(s) before first use.
"""

DEFAULT_DEVICE = "GW-dev-test2"

# Azure subscription the test hub lives in. Preflight switches the az CLI
# default subscription to this when it differs (skipped for connection-string
# targets, where ARM is bypassed). Empty string = never switch.
TEST_SUBSCRIPTION = "Azure via Midpoint - Smartlift Test"

# Known test AR number (exists in SmartFleet). --auto sends it in the
# la.write.ar-number attempt; AHL rejects the write by design (read-only
# param 96), 1K persists it.
TEST_AR_NUMBER = "991337"

# Devices the harness may target. Add bench device ids here, NEVER prod ids.
TEST_DEVICE_ALLOWLIST: set[str] = {"GW-dev-test2"}

# Test IoT hub name(s). EMPTY = harness refuses to run (fill me in).
TEST_HUB_ALLOWLIST: set[str] = {"aritco-test01-iothub"}

# Safe params for --auto mode: cosmetic LIGHTING params only — RW in the
# AHL db (src/lib/ahl_lib.py) with value ranges taken from the param spec
# (AHL-COMMON/trunk/doc/spec/Smartlift Parameters.xlsx, rev 19; the Gateway
# access column there is only maintained for the AHL2 params 742+, so db
# access is authoritative for the older ids). The value cycle holds only
# spec-legal values (min/max/increment respected); auto mode writes the
# first cycle value that differs from the current one and restores the
# original afterwards. Deliberately excluded: door dwell times, floor
# level adjusts, lubrication counters, locks, customer id, reset (98),
# register hashes, alarm-acknowledge registers. NEVER add motion/safety
# params here.
#
# Grouped by value shape: the gateway-side write path is identical for all
# params, so one param per class gives full software coverage. --auto picks
# ONE RANDOM param per class each run (repeated runs sweep all registers);
# --all-params cycles every param.
# (param id, name, safe value cycle)
SAFE_WRITE_PARAM_CLASSES: dict[str, list[tuple[int, str, list[str]]]] = {
    "bool": [
        (7, "Light switch", ["1", "0"]),
        (109, "Service Light", ["1", "0"]),
        (380, "Shaft rgbw toggle", ["0", "1"]),
        (381, "Shaft rgbw dim toggle", ["0", "1"]),
    ],
    "small-int": [
        (5, "Platform light on time", ["2", "3"]),   # 1-10 min
        (6, "Light dim time", ["5", "6"]),           # -1-60 min
        (44, "Light ramp up time", ["2", "3"]),      # 1-10 s
        (45, "Light ramp down time", ["5", "6"]),    # 1-10 s
    ],
    "step16": [
        (40, "Platform White Dim level", ["128", "144"]),  # 0-255 step 16
        (376, "Design wall temperature", ["0", "16"]),
        (377, "Design wall dim temperature", ["0", "16"]),
        (378, "Shaft white temperature", ["0", "16"]),
        (379, "Shaft white dim temperature", ["0", "16"]),
    ],
    "24bit": [
        (37, "Shaft Colour", ["16777215", "16777205"]),  # 0-0xFFFFFF, 2-register packing
    ],
}

SAFE_WRITE_PARAMS: list[tuple[int, str, list[str]]] = [
    param for cls in SAFE_WRITE_PARAM_CLASSES.values() for param in cls
]

# Never invoked by any group; future --danger work must keep these gated.
DANGER_METHODS: set[str] = {
    "gw.reboot",
    "la.send.reboot-request",
    "la.send.reset-service-memory",
    "la.fwu-trigger",
    "ca.fwu-trigger",
    "lcm.fwu-trigger",
}

# Implemented EG-64 DDMs (compressed envelope responses).
ENVELOPE_METHODS: set[str] = {
    "la.read.parameter",
    "la.read.parameters",
    "la.read.lift-type",
    "la.read.ar-number",
    "la.write.parameter",
    "la.write.read.parameter",
    "la.write.ar-number",
    "ca.download-file",
}

# Still log-only placeholders ({"result": true, "message": ...}); the
# non-destructive ones are probed in the read_only group.
PLACEHOLDER_METHODS: list[str] = [
    "gw.read.hostname",
    "gw.read.hw-version",
    "gw.read.bom-revision",
    "gw.read.serial-number",
    "la.script-request",
    "la.gw-log-generate",
    "la.lift-log-generate",
    "la.ll.send-request",
    "ca.set.config-item",
]

# ca.download-file security rejects — NO real blob needed: every case is
# rejected by validation before any network fetch. Each trips exactly ONE
# check. Hosts ending in .blob.core.windows.net match the device's
# DOWNLOAD_HOST_ALLOWLIST (verify against src/config.py).
# (case name, method payload, expected ec) — all return HTTP 200 with an
# error envelope.
DOWNLOAD_REJECT_CASES: list[tuple[str, dict, str]] = [
    (
        "bad-host",
        {"uri": "https://evil.example.com/c/x.sh?sig=1", "type": "0x0B"},
        "URL_ERR",
    ),
    (
        "traversal-filename",
        {
            "uri": "https://unit.blob.core.windows.net/c/..%2f..%2fetc%2fx.sh?sig=1",
            "type": "0x0B",
        },
        "FILE_NAME_ERR",
    ),
    (
        "unknown-type",
        {"uri": "https://unit.blob.core.windows.net/c/x.sh?sig=1", "type": "0xFF"},
        "TYPE_ERR",
    ),
]

# Malformed payloads → expect HTTP 400 + es=MethodRequestHandler ec=ARG_ERR.
# All are rejected by payload validation BEFORE any hardware/proxy call, so
# they are safe to send even against a connected lift.
MALFORMED_CASES: list[tuple[str, dict]] = [
    ("la.read.parameter", {}),
    ("la.read.parameter", {"parameter": "abc"}),  # the 2473acf regression
    ("la.read.parameters", {}),
    ("la.read.parameters", {"from": 5, "to": 3}),  # empty range -> no ids
    ("la.read.parameters", {"parameters": "12"}),  # scalar string, not a list
    ("la.read.parameters", {"from": 0, "to": 2000000000}),  # oversized range
    ("la.write.parameter", {"parameter": 1}),  # missing value
    ("la.write.parameter", {"parameter": "abc", "value": "1"}),
    ("la.write.read.parameter", {}),
    ("la.write.ar-number", {}),
    ("ca.download-file", {}),
]
