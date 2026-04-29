# Bluetooth API

Modern BLE service for the Aritco Gateway. Lives in `src/bluetoothApi/`.
Spec: `docs/superpowers/specs/2026-04-23-eg58-ble-design.md`.

## Overview

The gateway exposes a BLE GATT server with two services:

- A custom **WiFi service** (`de0a7b0d-358f-4cef-b778-000000000000`) for
  onboarding the gateway onto a WiFi network.
- The Bluetooth-standard **Device Information Service** (`0x180A`) for
  identifying the gateway (model, serial, hardware/software revision,
  manufacturer).

The WiFi service is notification-driven. Mobile subscribes to a single
**Status** characteristic and receives small "tick" notifications on every
state change plus a periodic heartbeat. Mobile reads the full Status from
the same characteristic on each tick to get the current state.

## Layout

```
src/bluetoothApi/
  state.py         Phase, ErrorCode, NetworkInfo, ConnectionInfo, Status
  wifi_cli.py      Async wrapper around /opt/nexyhub/wifi_connect.sh
  controller.py    State machine + asyncio.Lock + heartbeat ticker
  server.py        GATT lifecycle + 4 callbacks + DIS + advertising config
```

Dependency direction is strictly downward.

## WiFi service — `de0a7b0d-358f-4cef-b778-000000000000`

| Suffix | Name | Properties | Body |
|--------|------|------------|------|
| `…0001` | Status | read + notify | READ: full Status JSON. NOTIFY: small tick. |
| `…0002` | ScanRequest | write | `{}` or `{"force": true}` |
| `…0003` | ConnectRequest | write | `{"ssid": "...", "psk": "...", "iface": "wlan0\|ppp0"}` |
| `…0004` | Disconnect | write | `{}` |

### Status payload (READ)

```json
{
  "seq": 0,
  "phase": "idle",
  "iface": null,
  "current": null,
  "networks": [],
  "error": null,
  "last_updated_ms": 0
}
```

- **`seq`** — monotonic counter. Bumped on every state change and every
  heartbeat. Detect missed notifications via gaps.
- **`phase`** — `idle | scanning | connecting | connected | disconnected | error`.
- **`iface`** — `"wlan0" | "ppp0" | null`.
- **`current`** — `{ "ssid": str, "rssi": int, "ip": str }` when connected
  to wlan0, else `null`.
- **`networks`** — top-by-signal scan results, deduplicated by SSID. Capped
  at 4 entries to keep the full Status under the 512-byte GATT limit.
- **`error`** — `{ "code": str, "message": str }` when phase is error,
  else `null`. Codes: `PSK_TOO_SHORT`, `PSK_WRONG`, `SSID_NOT_FOUND`,
  `TIMEOUT`, `INVALID_REQUEST`.
- **`last_updated_ms`** — Unix epoch ms.

### Tick payload (NOTIFY)

Always under any MTU:

```json
{"seq":1234,"phase":"connecting","last_updated_ms":1719834567890}
```

## Mobile flow (indicate-and-fetch)

```
1. scan(deviceName: "Aritco Gateway")
2. connect, discover services
3. subscribe(Status)
4. on each NOTIFY:
     fullStatus = read(Status)
     parse JSON
     update UI
```

That's the entire protocol. Mobile never has to assemble state from
multiple characteristics or interpret status codes from raw bytes.

## Device Information Service (`0x180A`)

| UUID | Field | Source |
|------|-------|--------|
| `2A24` | Model | constructor (default `"46044-V1"`) |
| `2A25` | Serial | `AR_NUMBER` env var (empty if unset) |
| `2A27` | Hardware revision | constructor (default `"1.3"`) |
| `2A28` | Software revision | constructor (default `"2026.04"`) |
| `2A29` | Manufacturer | constructor (default `"Aritco Lift AB"`) |

## Configuration (env vars)

| Var | Default | Purpose |
|-----|---------|---------|
| `BLE_NAME` | `Aritco Gateway` | Advertised device name |
| `BLE_ADAPTER` | `hci0` | Host BLE adapter |
| `AR_NUMBER` | `""` | DIS Serial value |
| `BLE_ADV_INTERVAL_MS` | `152` | Advertising interval (see below) |
| `BLE_STATUS_REFRESH_MS` | `2000` | Heartbeat ticker period |

### Why `BLE_ADV_INTERVAL_MS = 152`?

Apple's *Accessory Design Guidelines* publishes a list of approved BLE
advertising intervals that align with the iOS scanner's timing. Sticking to
one of them gives reliable discovery on iPhones; arbitrary values can be
delayed or missed. The approved intervals are:

```
20 ms  152.5 ms  211.25 ms  318.75 ms  417.5 ms
546.25 ms  760 ms  852.5 ms  1022.5 ms  1285 ms
```

`152` ms is the closest integer to Apple's recommended `152.5` ms (BlueZ
takes integer ms). It gives ~0.3 s discovery latency — perceptually
instant — while keeping the radio idle for most of the time. We
deliberately do not run at the 20 ms "fast" value: BLE is used rarely
(install + occasional reconfig), so the always-on cost of 50 adv/sec on a
mains-powered gateway is wasted RF and a tiny ~30 Wh/yr power penalty for
no perceptual gain.

## Manual hardware test

1. Flash gateway, start container. Logs show `Starting Aritco Gateway BLE service`.
2. Mobile app finds `Aritco Gateway` within ~0.3s (vs ~30s on legacy).
3. Subscribe to Status — receive immediate tick with `phase=idle`.
4. Write `{}` to ScanRequest. Receive ticks → READ shows `phase=scanning`,
   then `phase=idle` with networks list.
5. Write `{"ssid":"X","psk":"hunter222","iface":"wlan0"}` to ConnectRequest.
6. Receive ticks → READ shows `phase=connecting`, then either
   `phase=connected` with `current.ip` populated, or `phase=error` with a
   typed code.
7. Disconnect BLE — RS232/RS485 handlers continue in parallel (EG-58 DoD).

## References

- Spec: `docs/superpowers/specs/2026-04-23-eg58-ble-design.md`
- Plan: `docs/superpowers/plans/2026-04-23-eg58-ble-characteristics.md`
- Esse-ti SDK: `../Esse-ti/delivery/`
