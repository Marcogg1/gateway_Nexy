# Feature Specification: Background lift re-identification when lift type is UNKNOWN

**Feature Branch**: `AIOT-183-lift-reidentification`

**Created**: 2026-08-25

**Status**: Draft

**JIRA**: [AIOT-183](https://aritco.atlassian.net/browse/AIOT-183) (Bug, Major, component IoT Gateway, parent epic AIOT-53). Supersedes legacy EG-50.

**Input**: User description: "AIOT-183 Background lift re-identification when lift type is UNKNOWN. Since EG-72, an unidentified lift no longer aborts startup — the cloud stack boots and stays online. But identification runs exactly once at startup and nothing ever re-probes. If the gateway boots before the lift is powered (AUD-004 commissioning scenario), UNKNOWN is permanent for the power cycle: polling no-ops, the lift-type twin report is skipped so the cloud keeps a stale value, all lift DDMs return INIT_ERR envelopes, heartbeats report a healthy device shipping zero lift data. Only a manual reboot recovers. Fix: (1) background re-identification while UNKNOWN, switching to the identified lift handler on success; (2) report lift type "unknown" to the device twin while unidentified, the real type once identified. Acceptance: gateway powered before lift boots UNKNOWN, twin shows liftType unknown; once the lift powers up, identification succeeds within one retry interval without restart, twin updates to the real type, lift DDMs/polling start working. Unit tests for the retry task and both twin reports."

## Background

The gateway is a separate device from the lift controller it serves. During installation and after maintenance the two are routinely powered in either order, and the lift controller can be power-cycled independently of the gateway. Today the gateway decides *once*, during its own startup, which kind of lift (if any) is attached. If that decision lands on "unknown" the gateway stays online but useless for lift data until someone physically restarts it — and nothing in the cloud tells the fleet operator that this is the state the device is in.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Gateway self-recovers when the lift comes up later (Priority: P1)

An installer powers the gateway before the lift controller (or the lift is switched off for service while the gateway stays up). The gateway boots, reports itself online, and — once the lift controller is powered and responding — automatically detects the lift and starts serving lift data, direct methods and polling **without anyone restarting the gateway**.

**Why this priority**: This is the defect itself. Without it, every "gateway before lift" power-up sequence in the field produces a permanently blind gateway until a truck roll or a remote reboot. It directly blocks commissioning and undermines the AUD-004 / EG-72 startup-resilience work.

**Independent Test**: On a bench, start the gateway with the lift controller off (or serial cable unplugged). Confirm the gateway is online and reports an unknown lift. Power the lift (plug the cable). Within the recovery target (see SC-001) the gateway reports the real lift type and lift reads succeed — no gateway restart.

**Acceptance Scenarios**:

1. **Given** the gateway has booted with no lift responding, **When** the lift controller becomes responsive, **Then** the gateway identifies the lift within the recovery target and lift polling begins delivering parameter data.
2. **Given** the gateway has booted with no lift responding, **When** a cloud user invokes a lift direct method before the lift is up, **Then** the gateway answers with the existing "not initialised" error envelope (unchanged behaviour), **and When** the same method is invoked after the lift has been identified, **Then** it succeeds.
3. **Given** the gateway is in the unknown state, **When** the lift never becomes responsive, **Then** the gateway keeps retrying at a bounded cadence indefinitely without exhausting resources, without flooding logs, and without affecting cloud connectivity, heartbeats or remote reboot capability.
4. **Given** re-identification has succeeded, **When** the lift is later power-cycled again, **Then** existing behaviour applies (identification is not re-run for an already identified lift; this feature only covers the unknown→identified transition).

---

### User Story 2 - Fleet sees "unknown lift" instead of stale data (Priority: P2)

A fleet operator looking at a gateway in SmartFleet / the device twin can tell that the gateway is up but has **not** identified a lift, rather than seeing the lift type from a previous power cycle and assuming all is well.

**Why this priority**: Turns a silent failure into a visible, actionable state. Lower than P1 because P1 removes most occurrences; P2 covers the residual (lift truly absent / faulty cable) so support can act on it.

**Independent Test**: Boot the gateway with no lift. Read the device twin reported properties: the lift-type field must show the unknown value. Power the lift; after identification the field must show the real type.

**Acceptance Scenarios**:

1. **Given** the gateway boots and identification fails, **When** the cloud reads the reported twin, **Then** the lift-type property carries the "unknown" value — never the previous boot's value.
2. **Given** the gateway is reporting unknown, **When** background identification succeeds, **Then** the lift-type property is updated to the identified type within one twin-report cycle of identification.
3. **Given** identification succeeded at first attempt (today's normal path), **When** the twin is read, **Then** behaviour is identical to today (real type reported once at startup).

---

### User Story 3 - All cloud-facing surfaces agree on the lift type after recovery (Priority: P3)

After a late identification, every place the gateway exposes the lift type — the twin, the `la.read.lift-type` direct method, and the per-message lift-type tag on telemetry — reports the same, current type. No surface keeps the boot-time "unknown" snapshot.

**Why this priority**: Consistency requirement that only matters once P1 exists. Cheap to get wrong (surfaces that cache the type at startup) and confusing for Backend / SmartFleet if two fields disagree.

**Independent Test**: After a bench recovery (US1), invoke `la.read.lift-type` and inspect a telemetry message's lift-type tag; both must match the twin's reported type.

**Acceptance Scenarios**:

1. **Given** the gateway recovered from unknown to an identified lift, **When** telemetry is sent, **Then** its lift-type tag reflects the identified type, not "unknown".
2. **Given** the same recovery, **When** `la.read.lift-type` is invoked, **Then** it returns the identified type's code.

---

### Edge Cases

- **Lift responds partially / intermittently** during a probe (noisy line, lift mid-boot): a failed probe must simply count as "still unknown" and be retried; it must not leave the gateway half-initialised.
- **Serial port contention**: while unknown, both candidate serial links (RS485 for AHL, RS232 for 1000-series) remain in use for probing. Once identified, the losing link must be released so it does not hold the port or leak handles (relates to audit item AUD-033). Nothing else in the app may open those ports while probing is in progress.
- **Lift becomes responsive during a probe cycle**: identification succeeds on the next attempt; no double-initialisation of the lift handler.
- **Cloud disconnected while identification succeeds offline**: identification itself never depends on the cloud (Principle VIII), and the lift-type report is attempted as soon as the lift is identified. The existing twin reporter is fire-and-forget, so a patch attempted while offline is **lost** and the twin keeps its previous value until the next report — re-sending reported properties on reconnect is out of scope here and tracked in **AIOT-189**. Bench row T1b records the observed behaviour.
- **Remote reboot / service-reset direct methods while unknown**: must keep working as today; re-identification runs in the background and must never block the method-handling path.
- **Shutdown while a probe is in flight**: the background task is cancelled cleanly and no further probe round is started. The in-flight probe runs in a worker thread, so its current transaction still completes on the bus (up to the handler's serial timeout) before the process exits; wiring handler close() into shutdown is out of scope here.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: While the lift type is unknown, the gateway MUST periodically re-attempt lift identification in the background, at a bounded, regular cadence, for as long as the process runs.
- **FR-002**: On a successful re-identification the gateway MUST switch to the identified lift's handler so that polling, direct methods, parameter reads/writes and telemetry behave exactly as they would after a successful startup identification.
- **FR-003**: Re-identification MUST NOT block, delay or degrade any other gateway function (cloud connection, heartbeats, direct-method handling, BLE onboarding, remote reboot).
- **FR-004**: When startup identification fails, the gateway MUST report the lift-type reported-property with the "unknown" value so the cloud never retains a previous boot's value.
- **FR-005**: When background identification succeeds, the gateway MUST report the identified lift type to the reported twin.
- **FR-006**: After a late identification, every surface that exposes the lift type (reported twin, `la.read.lift-type`, telemetry lift-type tag) MUST reflect the current type; no component may keep a startup-time snapshot.
- **FR-007**: Once identification succeeds, the gateway MUST release the serial link of the non-matching lift family (and MUST keep both links available for probing while unknown).
- **FR-008**: A failed probe MUST leave the gateway in the same "unknown" state it was in before the probe (no partial initialisation, no leaked resources).
- **FR-009**: The background task MUST stop cleanly on application shutdown, and MUST be supervised so that an unexpected error in it is logged and does not silently end retries (coordinate with EG-61 task supervision in `main()`).
- **FR-010**: Repeated failures MUST NOT flood logs: after the first failure, further "still unknown" messages are rate-limited (e.g. one summary line per N attempts), and success is always logged once.
- **FR-011**: Unit tests MUST cover: the retry loop (keeps retrying while unknown, stops when identified, stops on cancellation), the "unknown" twin report at startup, the identified-type twin report after late identification, and the surfaces in FR-006.

### Key Entities

- **Lift type state**: one of *unknown*, *AHL*, *1000-series*. Lives in the lift proxy; the only value that transitions at runtime under this feature is *unknown → identified*.
- **Lift-type reported property** (`gw.liftType`): the cloud-visible mirror of the state. Value set for unknown follows the existing lift-type enum's textual value for unknown, consistent with how identified types are reported today; the migration to numeric legacy codes is tracked separately in EG-71 and MUST apply uniformly to all three values there.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With the gateway booted before the lift, the lift is identified and lift data flows within **60 seconds** of the lift controller becoming responsive, with **no gateway restart**.
- **SC-002**: The reported twin shows the "unknown" lift type within one twin-report cycle of a failed startup identification, and the real type within one cycle of a successful late identification — verified on the bench by reading the twin.
- **SC-003**: A gateway left in the unknown state for **≥ 24 h** on the bench shows no growth in open file handles or memory attributable to the retry task and keeps heartbeating normally.
- **SC-004**: 100 % of the existing lift-proxy / startup unit tests still pass, plus new tests for FR-011; `python -m mypy .` clean.
- **SC-005**: Field-level: "gateway online but no lift data after installation" support cases that are resolved by a gateway reboot drop to zero for gateways running this build.

## Hardware & Field Impact *(constitution Principle VI)*

1. **Backward compatibility** — no change to direct-method names/payloads or telemetry shape. The reported property `gw.liftType` gains one additional value ("unknown") that older gateways never emitted; Backend/SmartFleet consumers must tolerate it (today they already tolerate the field being absent). Coordinate with Backend per Principle VII; no Backend code change expected. Legacy `smartlift2` tooling reads `la.read.lift-type` code `"0"` for unknown — unchanged.
2. **OTA / image compatibility** — application-only change inside the container; no image-format, base-image or dockerd implications.
3. **Hardware test plan** — AHL bench (RS485) and 1000-series bench (RS232), plus `tests/iot-test` harness for the twin/telemetry assertions:
   - T1 gateway up, lift off → twin unknown; power lift → identified ≤ 60 s, polling and a lift DDM succeed (both lift families).
   - T2 gateway up, serial cable unplugged for ≥ 1 h → no resource growth, heartbeats steady; plug cable → recovery.
   - T3 normal power order (lift first) → behaviour identical to today.
   - T4 remote reboot DDM while unknown → works.
   - Estimated bench time: **~3 h** (2 rigs × ~1 h + harness runs). `tasks.md` MUST carry this task.
4. **Safety relevance** — no lift control-path change. Identification probes are read-only bus queries already issued at startup today; the only new behaviour is issuing them repeatedly while no lift is identified, and releasing the loser's serial port. Flagged **not safety-relevant**, but bench test T1 must confirm probing does not disturb the lift controller when it boots mid-probe.

## Offline behaviour *(constitution Principle VIII)*

Identification and re-identification are purely local (serial bus); they run regardless of cloud state, and loss of cloud connectivity neither starts nor stops re-identification. The lift-type twin report is attempted once per state change and is bounded by a timeout so a stalled patch cannot block the lift loops; it is **not** queued or retried on reconnect today — that gap is **AIOT-189**.

## Assumptions

- **Retry cadence**: identification is retried at a fixed cadence in the order of the existing identification retry delay / polling interval (≈ 5 s per probe cycle); the planning phase chooses the exact value and whether one "cycle" is a single probe or the existing 10-attempt burst. SC-001's 60 s target bounds the choice. No exponential backoff — the cost of a probe is negligible and fast recovery matters more.
- **Unknown twin value**: reuse the lift-type enum's existing value for unknown, so the three values are reported the same way; EG-71 owns the numeric-code migration for all of them.
- **Scope boundary**: only the *unknown → identified* transition is handled. Detecting that an identified lift went away, or that the lift *family* changed at runtime, is out of scope (would need a different identification model; file separately if wanted).
- **AUD-033 (release losing serial link)** is pulled into scope (FR-007) because re-probing keeps both links alive longer than today and makes the leak observable; it is small and in the same code area.
- **EG-50** is superseded by this ticket; propose closing EG-50 as *Duplicate* with a link to AIOT-183 (needs dev confirmation before any JIRA action).
- **Task supervision (EG-61)** is not implemented here; FR-009 only requires the new task to fail loudly and be cancellable, so it fits whatever supervision EG-61 lands.
- Existing unit-test conventions (`unittest` under `utest/`, patched sleeps, no hard-coded counts) apply.
