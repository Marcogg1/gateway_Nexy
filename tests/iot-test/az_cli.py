"""Single choke point for all Azure CLI calls made by the harness.

Every command runs as ``az ... -o json``. Non-zero az exit raises
``AzCliError``. A module-global dry-run mode prints the command instead of
executing and returns ``None`` so callers can mark tests SKIPped.

Windows note: ``az`` is ``az.cmd``; ``shutil.which`` resolves it so
``subprocess`` can run it without ``shell=True``.
"""

import json
import re
import shutil
import subprocess
import time
from collections.abc import Iterator
from typing import Any

DRY_RUN = False
VERBOSE = False


class AzCliError(RuntimeError):
    """An az command failed or the CLI is unusable."""


def is_connection_string(hub: str) -> bool:
    """True if hub is an IoT Hub connection string rather than a hub name."""
    return "HostName=" in hub


def hub_name_of(hub: str) -> str:
    """Plain hub name, whether hub is a name or a connection string."""
    if not is_connection_string(hub):
        return hub
    host = next((p.removeprefix("HostName=") for p in hub.split(";")
                 if p.startswith("HostName=")), "")
    return host.split(".")[0]


def hub_args(hub: str) -> list[str]:
    """az iot target args: --login <cs> bypasses ARM (no subscription RBAC
    needed), --hub-name <name> resolves the hub through ARM."""
    if is_connection_string(hub):
        return ["--login", hub]
    return ["--hub-name", hub]


def _az_exe() -> str:
    """Resolve the az executable, raising if the CLI is not installed."""
    exe = shutil.which("az")
    if exe is None:
        raise AzCliError("Azure CLI ('az') not found on PATH. Install it and run 'az login'.")
    return exe


def run_az(args: list[str], timeout: int = 120) -> Any:
    """Run ``az <args> -o json`` and return the parsed JSON (or None in dry-run).

    Args:
        args: az arguments WITHOUT the leading 'az' and without '-o json'.
        timeout: Hard subprocess timeout in seconds (bounded by design).

    Raises:
        AzCliError: on non-zero az exit, timeout, or unparseable output.
    """
    if DRY_RUN:
        shown = " ".join(args)
        shown = re.sub(r"SharedAccessKey=[^;\s]+", "SharedAccessKey=***", shown)
        print(f"  DRY-RUN: az {shown} -o json")
        return None
    head = args[0] if args else "?"
    cmd = [_az_exe(), *args, "-o", "json"]
    if VERBOSE:
        shown = re.sub(r"SharedAccessKey=[^;\s]+", "SharedAccessKey=***", " ".join(args))
        print(f"  $ az {shown}")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise AzCliError(f"az {head} timed out after {timeout}s") from exc
    if proc.returncode != 0:
        raise AzCliError(f"az {' '.join(args[:4])} failed: {proc.stderr.strip()[:500]}")
    text = proc.stdout.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except ValueError as exc:
        raise AzCliError(f"az {head} returned non-JSON output: {text[:200]}") from exc


def invoke_method(hub: str, device: str, method: str,
                  payload: dict | None, response_timeout: int = 30) -> dict | None:
    """Invoke a direct method; returns {'status': int, 'payload': ...} or None (dry-run)."""
    return run_az([
        "iot", "hub", "invoke-device-method",
        *hub_args(hub), "--device-id", device,
        "--method-name", method,
        "--method-payload", json.dumps(payload if payload is not None else {}),
        "--timeout", str(response_timeout),
    ], timeout=response_timeout + 30)


def twin_show(hub: str, device: str) -> dict | None:
    """Return the full device twin (or None in dry-run)."""
    return run_az(["iot", "hub", "device-twin", "show",
                   *hub_args(hub), "--device-id", device])


def twin_update_desired(hub: str, device: str, patch: dict) -> dict | None:
    """Patch desired properties; a None value in the patch removes the key."""
    return run_az(["iot", "hub", "device-twin", "update",
                   *hub_args(hub), "--device-id", device,
                   "--desired", json.dumps(patch)])


def account_show() -> dict | None:
    """Current az subscription context."""
    return run_az(["account", "show"])


def account_set(subscription: str) -> None:
    """Switch the az CLI default subscription (persists outside this run)."""
    run_az(["account", "set", "--subscription", subscription])


def iot_extension_present() -> bool:
    """True if the azure-iot CLI extension is installed."""
    try:
        run_az(["extension", "show", "--name", "azure-iot"])
        return True
    except AzCliError:
        return False


def start_monitor(hub: str, device: str, consumer_group: str,
                  window_s: int) -> subprocess.Popen | None:
    """Start ``az iot hub monitor-events`` in the background.

    NOTE: az's ``--timeout`` is an INACTIVITY timeout, not an absolute
    duration — on a chatty hub the process never exits by itself, so the
    caller MUST bound it via ``collect_monitor`` (communicate + kill).
    """
    if DRY_RUN:
        print(f"  DRY-RUN: az iot hub monitor-events --hub-name {hub_name_of(hub)} "
              f"--device-id {device} --consumer-group {consumer_group} "
              f"--timeout {window_s} --props all -o json")
        return None
    # Read from slightly in the past: az attaches to the event hub at "now",
    # which is 5-15 s after Popen (CLI cold start + AMQP handshake). Events
    # published in that gap would otherwise be missed.
    enqueued_ms = int((time.time() - 5) * 1000)
    cmd = [_az_exe(), "iot", "hub", "monitor-events",
           *hub_args(hub), "--device-id", device,
           "--consumer-group", consumer_group,
           "--timeout", str(window_s),
           "--enqueued-time", str(enqueued_ms),
           "--props", "all", "--yes", "-o", "json"]
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace")


def collect_monitor(proc: subprocess.Popen, window_s: int) -> list[dict]:
    """Collect monitor output; kill and drain on overrun.

    az's --timeout is an INACTIVITY timer measured from the last event, and
    a stray heartbeat resets it - so allow attach (~15 s) plus one reset on
    top of the window before killing. Killing loses az's buffered stdout
    (events included), so the margin must make a clean exit the norm.
    """
    err = ""
    try:
        out, err = proc.communicate(timeout=window_s * 2 + 30)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            out, err = proc.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            out = ""
    events = parse_event_stream(out or "")
    # monitor-events failing (missing consumer group, missing uamqp, RBAC)
    # looks identical to a quiet hub - surface stderr when nothing was seen.
    if not events and err and err.strip():
        print(f"  monitor-events stderr: {err.strip()[:300]}")
    return events


def parse_event_stream(text: str) -> list[dict]:
    """Parse monitor-events output: a stream of concatenated JSON objects."""
    events: list[dict] = []
    dec = json.JSONDecoder()
    i, n = 0, len(text)
    while i < n:
        while i < n and text[i] not in "{[":
            i += 1
        if i >= n:
            break
        try:
            obj, end = dec.raw_decode(text, i)
            events.append(obj)
            i = end
        except ValueError:
            i += 1
    return events


def event_payloads(events: list[dict]) -> Iterator[tuple[dict, dict]]:
    """Yield (payload_dict, event_dict) for each event with a JSON payload.

    monitor-events wraps each message as {"event": {...,"payload": ...}};
    payload arrives as a dict (json content-type) or a string to parse.
    """
    for e in events:
        if not isinstance(e, dict):
            continue
        ev = e.get("event", e)
        if not isinstance(ev, dict):
            continue
        p = ev.get("payload")
        if isinstance(p, str):
            try:
                p = json.loads(p)
            except ValueError:
                continue
        if isinstance(p, dict):
            yield p, ev
