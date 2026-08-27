# GatewayApp

Python 3.14 gateway application for Aritco lift systems. Connects lift
equipment (AHL via Modbus/RS485, 1000-series via RS232) to Azure IoT Hub for
cloud monitoring and management: telemetry, device twin, direct methods (DDMs),
BLE WiFi onboarding, blob file transfer.

Merges three legacy repositories: `aritco-gw-cloud-agent` (C++),
`bluetooth_api` (C++), `smartlift2` (Python 3.6).

## Dev setup (PC)

```bash
pip install -r requirements_host.txt   # dev/test dependencies
pytest utest/                          # run unit tests
python utils/delivery_check.py -a -x -l -u   # full CI check (tests+mypy+lint)
python -m mypy .                       # type check only
```

- Main branch: `dev`. Feature branches: `AIOT-<id>-short-description` (JIRA project AIOT; legacy Esse-ti Gateway tickets `EG-XX-description`). Spec Kit pipeline per `CLAUDE.md`.
- See `CLAUDE.md` for coding standards.

## Build & deploy the image

Use the build script — it handles the parts a plain `docker build` gets wrong
(`linux/arm64` platform, classic single-manifest tar for the gateway's legacy
dockerd, unique timestamp tag so re-uploads don't break the running
container's image reference):

```powershell
scripts/build_image.ps1        # Windows (scripts/build_image.sh on Linux/mac)
```

Output: `build/gateway-dev.tar` + tag `gateway:dev<MMddHHmm>`. Override via
env: `IMAGE_TAG`, `DOCKERFILE` (default `Dockerfile.dev`), `PLATFORM`, `OUTPUT`.

Deploy (printed by the script too):
1. LuCI > Docker > Images > Load → upload the `.tar`
2. LuCI > Docker > Containers > \<slot\> → set Image to the new tag → Save
3. Run Application = ON so the ENTRYPOINT fires (starts sshd)

Dev image env: `SSH_ENABLED=true`, `SSH_ROOT_PASSWORD=<required for sshd>`,
`SSH_PORT=22`.

## Running on the gateway

The app **is** the container: `entrypoint.sh` starts init scripts (sshd in the
dev image), then `exec python src/main.py` as PID 1. Container up = app
running. App exit = container exit.

Inspect over SSH (dev image):

```bash
ssh root@<gw-ip>
ps aux | grep main.py        # should be PID 1
tail -f /src/logs/<latest>   # app logs
```

Manual start (only if the container CMD was overridden):

```bash
cd /src && /opt/venv/bin/python src/main.py
```

- Use `/opt/venv/bin/python` explicitly — Docker `ENV PATH` does not reach SSH
  login shells.
- **Never run two instances**: same device identity kicks itself off IoT Hub
  in a loop (MQTT) and both fight over the serial port.

## Device identity (DPS)

The app provisions via Azure DPS (`global.azure-devices-provisioning.net`,
scope id in `src/config.py`). X509 auth: **`Config.DEVICE_NAME` must equal the
certificate CN exactly** — a mismatch gives MQTT `Connection Refused: not
authorised` at provisioning. Cert/key paths: `Config.TT_CERT` / `TT_KEY`
(PEM files in `src/`, not committed).

On success the log prints the assigned hub:
`Device provisioned to hub: <hub-name>` — that's the `--hub` value for tooling.

> **No supervision:** nothing restarts this process today — no container
> restart policy, no `HEALTHCHECK`, and NexyHub's crash behaviour is
> unconfirmed (pending Esse-ti answer). A fatal exit therefore requires
> manual intervention; DPS/connect failures retry forever instead of
> exiting (EG-72), and an unidentified lift stays online, reports
> `gw.liftType: "unknown"` and keeps re-probing in the background until a
> lift answers (AIOT-183) — no restart needed.

Common startup failures:

| Symptom | Cause |
|---|---|
| `Temporary failure in name resolution` | No DNS/uplink in container — check `/etc/resolv.conf`, then raw connectivity |
| `Connection Refused: not authorised` | `DEVICE_NAME` != cert CN, clock skew (check `date`), or cert not enrolled |

## Acceptance testing

### Test suites: CI vs bench-only

| Suite | Where it runs | Needs |
|-------|---------------|-------|
| `utest/` | CI (Azure Pipelines) + local | nothing — fully mocked |
| `tests/iot-test/` | bench only (manual) | live IoT Hub + running gateway |
| `tests/test_blob_integration.py` | bench only (manual) | Azure storage credentials |

CI runs `utils/delivery_check.py -a -x -l -u`, which executes `utest/` only.
The bench suites are operator tools and are never collected in CI — run
`pytest utest/` locally, not bare `pytest` from the repo root.

`tests/iot-test/` — service-side DDM acceptance harness (runs on the dev PC
against a live GW through IoT Hub). See `tests/iot-test/README.md` for setup;
quick form:

```bash
python tests/iot-test/iot_test.py --hub <test-hub> --dry-run        # sanity
python tests/iot-test/iot_test.py --hub <test-hub>                  # read-only
python tests/iot-test/iot_test.py --hub <test-hub> --bench --write-param 1 --write-value 7
```

`tests/test_blob_integration.py` — end-to-end blob upload/download against
real Azure (provision + upload + download + verify).
