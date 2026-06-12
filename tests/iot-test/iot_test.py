"""Service-side acceptance harness for GatewayApp DDMs.

Drives Azure IoT Hub from the dev PC: invokes direct methods, patches the
desired twin, monitors telemetry, and asserts the EG-64 compressed-envelope
contract. See tests/iot-test/README.md.

Usage (bench GW on the test hub):
    python tests/iot-test/iot_test.py --hub <test-hub> --bench \
        --write-param 1 --write-value 7
"""

import argparse
import json
import random
import sys
import time
from dataclasses import dataclass, field

import az_cli
import envelope
import iot_config


@dataclass
class Result:
    group: str
    name: str
    status: str          # PASS | FAIL | SKIP
    reason: str = ""


@dataclass
class Runner:
    args: argparse.Namespace
    results: list[Result] = field(default_factory=list)
    # (param, original value) pairs still needing restore at end of an
    # --auto run (telemetry re-write + any failed in-cycle restore).
    pending_restore: list[tuple[int, str]] = field(default_factory=list)

    # -- plumbing ---------------------------------------------------------

    def record(self, group: str, name: str, ok: bool | None, reason: str = "") -> None:
        status = "SKIP" if ok is None else ("PASS" if ok else "FAIL")
        self.results.append(Result(group, name, status, reason))
        print(f"  [{status}] {group}/{name}" + (f" - {reason}" if reason else ""))

    def invoke(self, method: str, payload: dict) -> tuple[int | None, dict | None]:
        """Invoke a DDM; returns (status, body) or (None, None) in dry-run."""
        if method in iot_config.DANGER_METHODS:
            raise RuntimeError(f"danger method blocked: {method}")
        resp = az_cli.invoke_method(self.args.hub, self.args.device, method, payload)
        if resp is None:
            return None, None
        time.sleep(0.5)   # pace invocations (LCM abort-on-busy floor)
        return resp.get("status"), resp.get("payload")

    # -- guardrails -------------------------------------------------------

    def preflight(self) -> bool:
        hub_name = az_cli.hub_name_of(self.args.hub)
        print(f"Target: hub={hub_name} device={self.args.device}")
        if not self.args.unsafe_target:
            if self.args.device not in iot_config.TEST_DEVICE_ALLOWLIST:
                print(f"REFUSED: device '{self.args.device}' not in "
                      f"iot_config.TEST_DEVICE_ALLOWLIST {sorted(iot_config.TEST_DEVICE_ALLOWLIST)}. "
                      "Add it there or pass --unsafe-target.")
                return False
            if hub_name not in iot_config.TEST_HUB_ALLOWLIST:
                print(f"REFUSED: hub '{hub_name}' not in iot_config.TEST_HUB_ALLOWLIST "
                      f"{sorted(iot_config.TEST_HUB_ALLOWLIST)}. Fill in the test hub "
                      "name(s) in tests/iot-test/iot_config.py or pass --unsafe-target.")
                return False
        if self.args.dry_run:
            print("Dry-run: skipping az/account/twin checks.")
            return True
        if not az_cli.iot_extension_present():
            print("REFUSED: azure-iot extension missing. Run: az extension add --name azure-iot")
            return False
        try:
            account = az_cli.account_show()
            current = (account or {}).get("name")
            if (iot_config.TEST_SUBSCRIPTION and current != iot_config.TEST_SUBSCRIPTION
                    and not az_cli.is_connection_string(self.args.hub)):
                print(f"Switching az subscription: {current} -> {iot_config.TEST_SUBSCRIPTION}")
                az_cli.account_set(iot_config.TEST_SUBSCRIPTION)
                account = az_cli.account_show()
            if account:
                print(f"Subscription: {account.get('name')} ({account.get('id')})")
            twin = az_cli.twin_show(self.args.hub, self.args.device)
        except az_cli.AzCliError as exc:
            print(f"REFUSED: {exc}")
            return False
        if not twin:
            print("REFUSED: cannot read device twin (wrong hub/device or no access).")
            return False
        print(f"Device connectionState: {twin.get('connectionState')}")
        if twin.get("connectionState") != "Connected":
            print("WARNING: device not Connected - method calls will 404/timeout.")
        return True

    # -- auto mode ----------------------------------------------------------

    def auto_select(self) -> None:
        """Fill missing write/AR args from iot_config.SAFE_WRITE_PARAMS.

        The telemetry group needs ONE write target: first safe param that
        reads cleanly; target = first cycle value differing from current.
        Its original value is restored by auto_restore() after the groups
        (the write_readback cycle restores itself, but telemetry re-writes
        the target afterwards). AR number: iot_config.TEST_AR_NUMBER, a known
        SmartFleet test AR. Explicit flags win over auto.
        """
        if self.args.ar_number is None:
            self.args.ar_number = iot_config.TEST_AR_NUMBER
        if self.args.dry_run:
            pid, _, values = iot_config.SAFE_WRITE_PARAMS[0]
            self.args.write_param = self.args.write_param or pid
            self.args.write_value = self.args.write_value or values[0]
            return
        if self.args.write_param is None and self.args.write_value is None:
            for pid, name, values in iot_config.SAFE_WRITE_PARAMS:
                status, body = self.invoke("la.read.parameter", {"parameter": pid})
                if status != 200 or not envelope.resp_ok(body or {}):
                    continue
                current = envelope.value_of(body or {}, str(pid))
                target = next((v for v in values if v != current), None)
                if current is None or target is None:
                    continue
                self.pending_restore.append((pid, current))
                self.args.write_param, self.args.write_value = pid, target
                print(f"Auto: write param {pid} ({name}): {current} -> {target}, restore after")
                break
            else:
                print("Auto: no safe write param readable - write groups will SKIP")
        print(f"Auto: ar-number {self.args.ar_number} (write attempt; "
              "AHL rejects AR writes by design, 1K persists it)")

    def auto_restore(self) -> None:
        """Write original values back after an --auto run."""
        for pid, original in dict(self.pending_restore).items():
            try:
                status, body = self.invoke("la.write.parameter",
                                           {"parameter": pid, "value": original})
                it = (envelope.items(body or {})[:1] or [{}])[0]
                ok = status == 200 and it.get("s") == "0"
                print(f"Auto: restored param {pid} = {original}"
                      if ok else f"Auto: RESTORE FAILED for param {pid}: "
                                 f"status={status} {envelope.error_of(body or {})}")
            except Exception as exc:  # noqa: BLE001 - keep restoring the rest
                print(f"Auto: RESTORE FAILED for param {pid}: {exc!r}")

    def _auto_write_cycle(self) -> None:
        """Exercise write, readback, and write+read across safe params.

        Default: one RANDOM param per value-shape class (the write path is
        identical per class, so this is full software coverage; randomness
        sweeps all registers over repeated runs). --all-params cycles every
        param. Per param: read current -> la.write.parameter(target) ->
        la.read.parameter readback -> la.write.read.parameter(original),
        which tests the combined DDM AND restores the original value.
        A param whose restore fails stays in pending_restore for the
        end-of-run auto_restore().
        """
        if self.args.all_params:
            selection = iot_config.SAFE_WRITE_PARAMS
        else:
            selection = [random.choice(cls)
                         for cls in iot_config.SAFE_WRITE_PARAM_CLASSES.values()]
            print("  sampled params: "
                  + ", ".join(f"{name}({pid})" for pid, name, _ in selection))
        for pid, name, values in selection:
            p = str(pid)
            status, body = self.invoke("la.read.parameter", {"parameter": pid})
            if status is None:
                self.record("write_readback", f"{name}({p})", None, "dry-run")
                continue
            if status != 200 or not envelope.resp_ok(body or {}):
                self.record("write_readback", f"{name}({p})", None,
                            f"unreadable: {envelope.error_of(body or {})}")
                continue
            current = envelope.value_of(body or {}, p)
            target = next((v for v in values if v != current), None)
            if current is None or target is None:
                self.record("write_readback", f"{name}({p})", None,
                            f"no usable target (current={current})")
                continue

            status, body = self.invoke("la.write.parameter",
                                       {"parameter": pid, "value": target})
            it = (envelope.items(body or {})[:1] or [{}])[0]
            ok = (status == 200 and it.get("p") == p
                  and it.get("s") == "0" and it.get("v") == target)
            self.record("write_readback", f"{name}({p}):write", ok,
                        "" if ok else f"item={json.dumps(it)} {envelope.error_of(body or {})}")
            if not ok:
                continue
            self.pending_restore.append((pid, current))

            status, body = self.invoke("la.read.parameter", {"parameter": pid})
            got = envelope.value_of(body or {}, p)
            self.record("write_readback", f"{name}({p}):readback",
                        status == 200 and got == target,
                        f"wrote {target}, read {got}")

            status, body = self.invoke("la.write.read.parameter",
                                       {"parameter": pid, "value": current})
            it = (envelope.items(body or {})[:1] or [{}])[0]
            ok = (status == 200 and it.get("p") == p
                  and it.get("s") == "0" and it.get("v") == current)
            self.record("write_readback", f"{name}({p}):write.read-restore", ok,
                        "" if ok else f"item={json.dumps(it)} {envelope.error_of(body or {})}")
            if ok:
                self.pending_restore.remove((pid, current))

    # -- groups (implemented in later tasks) -------------------------------

    def group_read_only(self) -> None:
        p = str(self.args.read_param)

        status, body = self.invoke("la.read.parameter", {"parameter": self.args.read_param})
        if status is None:
            self.record("read_only", "la.read.parameter", None, "dry-run")
        else:
            ok = (status == 200 and envelope.is_envelope(body)
                  and envelope.resp_ok(body or {})
                  and len(envelope.items(body or {})) == 1
                  and envelope.items(body or {})[0].get("p") == p
                  and "v" in envelope.items(body or {})[0])
            self.record("read_only", "la.read.parameter", ok,
                        "" if ok else f"device error: {envelope.error_of(body or {})}")

        ids = [self.args.read_param, self.args.read_param + 1]
        status, body = self.invoke("la.read.parameters", {"parameters": ids})
        if status is None:
            self.record("read_only", "la.read.parameters[list]", None, "dry-run")
        else:
            got_ids = [i.get("p") for i in envelope.items(body or {})]
            ok = (status == 200 and envelope.is_envelope(body)
                  and got_ids == [str(i) for i in ids])
            self.record("read_only", "la.read.parameters[list]", ok,
                        envelope.error_of(body or {}))

        lo, hi = self.args.read_param, self.args.read_param + 2
        status, body = self.invoke("la.read.parameters", {"from": lo, "to": hi})
        if status is None:
            self.record("read_only", "la.read.parameters[range]", None, "dry-run")
        else:
            got_ids = [i.get("p") for i in envelope.items(body or {})]
            ok = (status == 200 and envelope.is_envelope(body)
                  and got_ids == [str(i) for i in range(lo, hi + 1)])
            self.record("read_only", "la.read.parameters[range]", ok,
                        envelope.error_of(body or {}))

        status, body = self.invoke("la.read.lift-type", {})
        if status is None:
            self.record("read_only", "la.read.lift-type", None, "dry-run")
        else:
            ok = (status == 200 and envelope.is_envelope(body)
                  and (body or {}).get("lt") in {"0", "1", "2"})
            self.record("read_only", "la.read.lift-type", ok, f"lt={body and body.get('lt')}")

        status, body = self.invoke("la.read.ar-number", {})
        if status is None:
            self.record("read_only", "la.read.ar-number", None, "dry-run")
        else:
            has_v = body is not None and "v" in body
            has_err = body is not None and "es" in body and "ec" in body
            ok = status == 200 and envelope.is_envelope(body) and (has_v or has_err)
            self.record("read_only", "la.read.ar-number", ok,
                        f"v={(body or {}).get('v')}" if has_v else envelope.error_of(body or {}))

        for method in iot_config.PLACEHOLDER_METHODS:
            status, body = self.invoke(method, {})
            if status is None:
                self.record("read_only", f"placeholder:{method}", None, "dry-run")
            else:
                ok = status == 200 and envelope.is_placeholder(body)
                self.record("read_only", f"placeholder:{method}", ok)

    def group_malformed(self) -> None:
        for method, payload in iot_config.MALFORMED_CASES:
            status, body = self.invoke(method, payload)
            name = f"{method}:{json.dumps(payload)[:40]}"
            if status is None:
                self.record("malformed", name, None, "dry-run")
                continue
            ok = (status == 400 and isinstance(body, dict)
                  and body.get("ec") == "ARG_ERR"
                  and body.get("es") == "MethodRequestHandler")
            self.record("malformed", name, ok,
                        "" if ok else f"status={status} body={json.dumps(body)[:120]}")

        status, _ = self.invoke("zz.no.such.method", {})
        if status is None:
            self.record("malformed", "unknown-method-404", None, "dry-run")
        else:
            self.record("malformed", "unknown-method-404", status == 404,
                        f"status={status}")

    def group_device_errors(self) -> None:
        """Device-side error envelopes: rejected before any hardware write."""
        status, body = self.invoke("la.read.parameter", {"parameter": 9999})
        if status is None:
            self.record("device_errors", "read-unknown-param", None, "dry-run")
        else:
            it = (envelope.items(body or {})[:1] or [{}])[0]
            ok = (status == 200 and envelope.is_envelope(body)
                  and (body or {}).get("es") == "LiftProxy"
                  and it.get("p") == "9999"
                  and it.get("ec") == "PARAM_NOT_IN_DB")
            self.record("device_errors", "read-unknown-param", ok,
                        "" if ok else f"body={json.dumps(body)[:120]}")

    def group_download_rejects(self) -> None:
        for name, payload, expected_ec in iot_config.DOWNLOAD_REJECT_CASES:
            status, body = self.invoke("ca.download-file", payload)
            if status is None:
                self.record("download_rejects", name, None, "dry-run")
                continue
            ok = (status == 200 and isinstance(body, dict)
                  and body.get("es") == "MethodRequestHandler"
                  and body.get("ec") == expected_ec)
            self.record("download_rejects", name, ok,
                        "" if ok else f"expected ec={expected_ec}, "
                        f"got status={status} body={json.dumps(body)[:120]}")

    def _write_args_ok(self, group: str) -> bool:
        """Write/telemetry groups need --bench plus --write-param/--write-value."""
        if not self.args.bench:
            self.record(group, "all", None, "needs --bench (no guarded SAFE_PARAMS yet)")
            return False
        if self.args.write_param is None or self.args.write_value is None:
            self.record(group, "all", None, "needs --write-param and --write-value")
            return False
        return True

    def group_write_readback(self) -> None:
        if self.args.auto:
            self._auto_write_cycle()
        elif self._write_args_ok("write_readback"):
            self._single_param_case()
        self._ar_number_case()

    def _single_param_case(self) -> None:
        """Manual mode: write/readback/write+read for --write-param only."""
        p, v = str(self.args.write_param), str(self.args.write_value)

        status, body = self.invoke("la.write.parameter",
                                   {"parameter": self.args.write_param, "value": v})
        if status is None:
            self.record("write_readback", "la.write.parameter", None, "dry-run")
        else:
            it = (envelope.items(body or {})[:1] or [{}])[0]
            ok = (status == 200 and envelope.is_envelope(body)
                  and it.get("p") == p and it.get("s") == "0" and it.get("v") == v)
            self.record("write_readback", "la.write.parameter", ok,
                        "" if ok else f"item={json.dumps(it)} {envelope.error_of(body or {})}")

        status, body = self.invoke("la.read.parameter", {"parameter": self.args.write_param})
        if status is None:
            self.record("write_readback", "readback", None, "dry-run")
        else:
            got = envelope.value_of(body or {}, p)
            self.record("write_readback", "readback", status == 200 and got == v,
                        f"wrote {v}, read {got} (cache echo - not persistence proof)")

        status, body = self.invoke("la.write.read.parameter",
                                   {"parameter": self.args.write_param, "value": v})
        if status is None:
            self.record("write_readback", "la.write.read.parameter", None, "dry-run")
        else:
            it = (envelope.items(body or {})[:1] or [{}])[0]
            ok = (status == 200 and it.get("p") == p
                  and it.get("s") == "0" and it.get("v") == v)
            self.record("write_readback", "la.write.read.parameter", ok,
                        "" if ok else f"item={json.dumps(it)} {envelope.error_of(body or {})}")

    def _ar_number_case(self) -> None:
        """Exercise la.write.ar-number per the lift type's contract.

        AHL stores the AR number in read-only param 96 and the app rejects
        writes by design (lift_proxy.write_ar_number) - assert the rejection
        envelope and that the stored AR is untouched. 1K supports the write
        (liftRef1) - assert the happy path and readback.
        """
        if not self.args.bench or self.args.ar_number is None:
            self.record("write_readback", "la.write.ar-number", None,
                        "needs --bench and --ar-number (or --auto)")
            return
        ar = self.args.ar_number

        status, body = self.invoke("la.read.lift-type", {})
        is_ahl = status == 200 and (body or {}).get("lt") == "1"

        status, before_body = self.invoke("la.read.ar-number", {})
        before = (before_body or {}).get("v") if status == 200 else None

        status, body = self.invoke("la.write.ar-number", {"value": ar})
        if status is None:
            self.record("write_readback", "la.write.ar-number", None, "dry-run")
            return
        if is_ahl:
            ok = (status == 200 and envelope.is_envelope(body)
                  and (body or {}).get("w") == ar
                  and (body or {}).get("s") == "-1"
                  and (body or {}).get("es") == "LiftProxy"
                  and (body or {}).get("ec") == "PARAM_READ_ONLY")
            self.record("write_readback", "la.write.ar-number[ahl-reject]", ok,
                        "" if ok else f"body={json.dumps(body)[:120]}")
        else:
            ok = (status == 200 and envelope.is_envelope(body)
                  and (body or {}).get("w") == ar
                  and (body or {}).get("s") == "0"
                  and (body or {}).get("v") == ar)
            self.record("write_readback", "la.write.ar-number", ok,
                        "" if ok else f"body={json.dumps(body)[:120]}")

        status, body = self.invoke("la.read.ar-number", {})
        got = (body or {}).get("v") if status == 200 else None
        if is_ahl:
            self.record("write_readback", "ar-number-unchanged",
                        status == 200 and got == before,
                        f"AR still {got} after rejected write")
        else:
            self.record("write_readback", "ar-number-readback",
                        status == 200 and got == ar,
                        f"wrote {ar}, read {got} (live hardware read)")

    def group_twin(self) -> None:
        if self.args.dry_run:
            az_cli.twin_update_desired(self.args.hub, self.args.device,
                                       {"downloadMaxBytes": 1048576})
            self.record("twin", "desired-patch-accepted", None, "dry-run")
            return
        twin = az_cli.twin_show(self.args.hub, self.args.device) or {}
        prev = twin.get("properties", {}).get("desired", {}).get("downloadMaxBytes")
        try:
            az_cli.twin_update_desired(self.args.hub, self.args.device,
                                       {"downloadMaxBytes": 1048576})
            twin2 = az_cli.twin_show(self.args.hub, self.args.device) or {}
            got = twin2.get("properties", {}).get("desired", {}).get("downloadMaxBytes")
            self.record("twin", "desired-patch-accepted", got == 1048576,
                        "hub-accept only; device applies on restart (patch-merge stub)")
        finally:
            if twin:
                az_cli.twin_update_desired(self.args.hub, self.args.device,
                                           {"downloadMaxBytes": prev})

    def _watch_for_ddm_event(self) -> tuple[bool, int]:
        """One monitored window: attach monitor, invoke write, scan events.

        Returns (found_ddm_source_event, total_events_seen).
        """
        proc = az_cli.start_monitor(self.args.hub, self.args.device,
                                    self.args.consumer_group,
                                    self.args.telemetry_window)
        if proc is None:                      # dry-run
            return False, -1
        time.sleep(5)                         # let the consumer attach first
        self.invoke("la.write.parameter",
                    {"parameter": self.args.write_param,
                     "value": str(self.args.write_value)})
        events = az_cli.collect_monitor(proc, self.args.telemetry_window)
        found = False
        for payload, _ev in az_cli.event_payloads(events):
            if (payload.get("event") == "la.parameters.update"
                    and payload.get("source") == "la.parameter.ddm"
                    and any(d.get("parameter") == self.args.write_param
                            for d in payload.get("data", []))):
                found = True
        return found, len(events)

    def group_telemetry(self) -> None:
        if not self._write_args_ok("telemetry"):
            return
        found, seen = self._watch_for_ddm_event()
        if seen == -1:
            self.record("telemetry", "ddm-write-source", None, "dry-run")
            return
        if not found:                          # monitor-events is lossy: one retry
            print("  ddm event not seen, retrying once with a fresh monitor...")
            found, seen2 = self._watch_for_ddm_event()
            seen += max(seen2, 0)
        self.record("telemetry", "ddm-write-source", found,
                    f"la.parameters.update source=la.parameter.ddm "
                    f"param={self.args.write_param} ({seen} events seen)")
        self.record("telemetry", "telemetry-flowing", seen > 0,
                    f"{seen} D2C events in window(s)")

    # -- orchestration ------------------------------------------------------

    GROUPS = ["read_only", "malformed", "device_errors", "download_rejects",
              "write_readback", "twin", "telemetry"]

    def run(self) -> int:
        if not self.preflight():
            return 2
        if self.args.auto:
            self.auto_select()
        selected = [self.args.only] if self.args.only else self.GROUPS
        for name in selected:
            print(f"\n== {name} ==")
            try:
                getattr(self, f"group_{name}")()
            except az_cli.AzCliError as exc:
                self.record(name, "az-cli-error", False, str(exc))
            except Exception as exc:  # noqa: BLE001 - one bad group must not eat the summary
                self.record(name, "harness-error", False, repr(exc))
        self.auto_restore()
        return self.summary()

    def summary(self) -> int:
        fails = [r for r in self.results if r.status == "FAIL"]
        skips = [r for r in self.results if r.status == "SKIP"]
        print(f"\n==== {len(self.results)} tests: "
              f"{len(self.results) - len(fails) - len(skips)} passed, "
              f"{len(fails)} failed, {len(skips)} skipped ====")
        for r in fails:
            print(f"  FAIL {r.group}/{r.name}: {r.reason}")
        if self.args.out:
            with open(self.args.out, "w", encoding="utf-8") as f:
                json.dump([r.__dict__ for r in self.results], f, indent=2)
            print(f"Results written to {self.args.out}")
        return 1 if fails else 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="GatewayApp IoT Hub DDM acceptance harness")
    p.add_argument("--hub", required=True,
                   help="IoT Hub name, or an IoT Hub 'service' policy connection "
                        "string (bypasses ARM - works without subscription RBAC). "
                        "Hub name must be in the iot_config allowlist either way.")
    p.add_argument("--device", default=iot_config.DEFAULT_DEVICE)
    p.add_argument("--only", choices=Runner.GROUPS, help="run a single group")
    p.add_argument("--bench", action="store_true",
                   help="bare-LCM bench mode: enables write tests, no restore")
    p.add_argument("--auto", action="store_true",
                   help="fully automated bench run: pick a safe write param "
                        "(iot_config.SAFE_WRITE_PARAMS) + current AR number, "
                        "restore the param afterwards; implies --bench")
    p.add_argument("--all-params", action="store_true",
                   help="with --auto: cycle EVERY safe param instead of one "
                        "random param per value-shape class")
    p.add_argument("--read-param", type=int, default=1,
                   help="param id for read tests (default 1)")
    p.add_argument("--write-param", type=int,
                   help="param id for write tests (REQUIRED for write/telemetry groups)")
    p.add_argument("--write-value", help="value for write tests")
    p.add_argument("--ar-number",
                   help="AR number for la.write.ar-number happy path "
                        "(default in --auto: iot_config.TEST_AR_NUMBER)")
    p.add_argument("--consumer-group", default="nhGwTest",
                   help="dedicated Event Hub consumer group (never $Default)")
    p.add_argument("--telemetry-window", type=int, default=15,
                   help="monitor inactivity timeout in seconds; az exits this "
                        "long after the last received event (bounded)")
    p.add_argument("--unsafe-target", action="store_true",
                   help="bypass hub/device allowlist (DANGEROUS - know what you target)")
    p.add_argument("--dry-run", action="store_true", help="print az commands, execute nothing")
    p.add_argument("--out", help="write results JSON here (gitignored: results*.json)")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


def main() -> int:
    args = parse_args()
    if args.auto:
        args.bench = True
    az_cli.DRY_RUN = args.dry_run
    az_cli.VERBOSE = args.verbose
    return Runner(args).run()


if __name__ == "__main__":
    sys.exit(main())
