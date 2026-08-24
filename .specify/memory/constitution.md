<!--
COMPONENT-LOCAL COPY — IoT Gateway (GatewayApp)
================================================
Inherits: AIoT Platform Constitution v1.0.1 (Last Amended 2026-06-30) from
  AIoTDevFoundations/.specify/memory/constitution.md
Synced:   2026-08-21 via AIoTDevFoundations/manifests/spec-kit-conform.md
Rule:     Principles I..IX below are the foundation's verbatim. Do NOT edit them here —
          amend in the foundation (PR to main), then re-run the conform prompt.
          Only the "Component-Local: IoT Gateway" section is owned by this repo.
          There is no automated sync; re-sync when the foundation version changes.
-->

# AIoT Platform Constitution

This constitution governs engineering practice across the AIoT platform — the four
component repositories (**SmartApp**, **SmartFleet**, **SmartLift API**, **IoT
Gateway**) and this foundations repository that holds shared standards. Component
repos inherit these principles; local conventions may extend but MUST NOT contradict
them.

## Core Principles

### I. Spec-First Development

Every non-trivial feature MUST flow through the Spec Kit pipeline:
`/speckit-specify` → `/speckit-plan` → `/speckit-tasks` → execution. The spec is
written before code. **Execution runs on Superpowers `subagent-driven-development`**
(invoked through `/speckit-implement`, which delegates rather than implementing
inline). Keep the two "SDD"s distinct: Spec-Driven Development is the pipeline (the
*what*); subagent-driven-development is the execution engine (the *how*). Bugs with a clear, contained root cause MAY be fixed directly;
bugs with fuzzy scope or cross-component impact MUST run through `/speckit-tasks` at
minimum. Improvements are judged by complexity — small refactors ship as a PR; cross-
cutting changes use the full pipeline.

**Rationale:** The pipeline exists to surface unknowns and align on shape before
implementation. Skipping it on unclear work produces rework; demanding it for obvious
fixes produces ceremony. The split is deliberate.

**Atlassian MCP is required.** Devs working on AIoT MUST have the Atlassian MCP
configured in their Claude Code setup. Without it the agent cannot post
clarifications, read PO answers, or transition tickets — defeating the spec-driven
workflow. Treat MCP setup as a prerequisite for usage; flag missing config as a
blocker, not a workaround.

**Agent-proposed JIRA sync.** When `/speckit-specify` or `/speckit-clarify` surfaces
unresolved questions for the product owner, the agent (Claude Code) MUST **propose**
posting the questions as a numbered JIRA comment and transitioning the ticket to
**Planning**, then wait for dev confirmation before executing. Devs review and edit
the proposed comment before it goes live. Automation runs through the dev, not
around them — the agent does not transition tickets or post comments without
explicit go-ahead.

### II. Single Driving Repo per Feature

Each feature has exactly one **driving repo** that owns the spec. Selection follows
the matrix in `manifests/developer.md`: single-component features drive in that repo;
multi-component features drive in the repo where the change originates (regulation
forcing Gateway behavior → Gateway drives; data-model overhaul → Backend drives;
cross-stack UX → SmartApp/SmartFleet drives). Non-driving repos involved in the
feature MUST contain a `ref.md` pointing to the driving spec, plus their own
`tasks.md` covering only repo-specific work.

**Rationale:** A single source of truth for each feature spec prevents drift. A
feature split across multiple specs in multiple repos cannot stay coherent.

### III. JIRA Traceability (NON-NEGOTIABLE)

All dev work MUST be traceable to a JIRA ticket in the `AIOT` project. This means:

- Spec folder: `specs/AIOT-<id>-short-description/`
- Branch: `AIOT-<id>-short-description`, branched from `dev` in the component
  repos. Changes to *this* foundations repo land via PR to `main` (it is
  main-only / trunk-based)
- Commit prefix: `AIOT-<id> - <short message>`
- Dev-initiated tickets MUST set `fixVersion` at creation — no empty-fixVersion
  exception for devs. If work is not worth a target version, it is not worth a
  ticket.

**Rationale:** Without enforced traceability the JIRA board diverges from reality.
Every commit, PR, and spec must answer the question "which ticket?" — and the answer
must be present in the artifact itself, not in someone's head.

### IV. PR-Gated Integration

All changes to component repos and to this foundations repo MUST land via pull
request. `main` is branch-protected; direct commits are blocked. PR review is the
mechanism by which the team aligns on changes — drive-by edits are rejected on
principle, not merit.

When a spec **diverges meaningfully** from its JIRA Description during execution
(scope expanded, UX changed, user-visible behavior shifted), the dev MUST post a
summarizing comment to the ticket so the product owner can sanity-check before merge.
Minor clarifications do not require a comment; behavior changes do.

**Rationale:** PR review catches both technical issues and product drift. Skipping it
trades a small short-term gain for unbounded long-term cost.

### V. Honest Status and Versioning

Tickets MUST reflect reality:

- **Dates** — when a ticket leaves Ready for dev, set `Start date` (today, or actual
  start) and `Due date` (honest estimate). Slippage is allowed and expected — update
  the date rather than letting it lie.
- **Resolution** — pick `Done` for happy path, `Won't Do` for declined work,
  `Duplicate` only for accidental duplicates. Do not mark declined work as `Done` to
  clear the board.
- **Priority** — file at honest severity (`Blocker` / `Critical` / `Major` / `Minor`
  / `Trivial`); do not inflate.
- **fixVersion** — set at create. May be moved during Planning if scope slips. MUST
  NOT be moved after Working on starts unless the release itself is slipping.

**Rationale:** Process artifacts are only useful if they are honest. A board where
dates lie and resolutions are cosmetic provides no signal — and silently corrupts
every downstream decision (capacity planning, release scoping, blocker triage).

### VI. Hardware-Aware Engineering

Changes touching the IoT Gateway MUST consider backward compatibility with deployed
firmware. A change that would break a lift in the field is not shippable, regardless
of how well it works in the lab. Hardware testing on a real lift or a hardware
simulator is REQUIRED before merging any Gateway PR. OTA-compatibility implications
MUST be flagged early in the spec process.

**Rationale:** The Gateway controls physical hardware in customer-installed lifts.
Bugs there are not abstract — they are physically reachable, sometimes safety-
relevant, and rolling them back requires partner action in the field. The bar is
correspondingly higher than for cloud-only components.

### VII. Cross-Component Coherence

The four components form one product. Changes that ripple across components MUST
coordinate before merging:

- API contract changes require sign-off from the consumer-side dev
  (SmartApp / SmartFleet / Gateway) on the Backend PR before merge.
- User-visible concept names (e.g. "trip", "schedule", "permission level") MUST
  stay in sync between SmartApp and SmartFleet. If one renames, the other follows in
  the same release.

**Rationale:** Partners experience the platform as one product. The internal split
into four repos is an implementation detail, not a justification for divergent UX
or contract drift.

### VIII. Graceful Degradation

Partner-facing features MUST behave gracefully when conditions deteriorate:

- **Connectivity** — SmartApp remains functional on 3G and on intermittent
  connections (lifts in basements, parking garages, weak-signal areas).
- **Component unavailability** — when one component is unreachable (Backend down,
  Gateway offline), the user-facing app MUST surface a clear state rather than
  crashing or hanging silently. Cached state used where applicable.
- **Gateway offline** — IoT Gateway MUST continue operating offline and sync state
  on reconnect. Loss of cloud connectivity is not a lift outage.

**Rationale:** Lifts get installed in places with poor connectivity. A premium
product that breaks when the network is weak is not premium — it is fragile.

### IX. Tier as Presentation Gate

The `Tier` concept (`Free` / `Standard` / `Premium`) is enforced at the
presentation layer, not by branching code paths. Feature visibility checks the
partner's tier; underlying code paths stay shared. Premium features accessed by
lower tiers MUST degrade visibly (e.g. surface a clear upgrade affordance) rather
than crashing or silently misbehaving.

**Rationale:** Tier-branched code paths drift apart over time and create
combinatorial test burden. A single code path with presentation gates is easier to
test, reason about, and evolve when tier definitions change.

## Release Discipline

SmartLift ships in **bundled releases** to Partners — `SmartLift X.Y` packaging all
four components — with **isolated component patches** between bundles for
anti-logjam shipments.

- **Bundle versioning** — `SmartLift 5.0`, `5.1`, `6.0`. Major bump is a judgment
  call, not driven by breaking-change rules.
- **Isolated patch versioning** — `<Component> <bundle-era>.<patch-num>`, e.g.
  `SmartApp 5.0.1`. Patch counter is per-component and resets at the next bundle.
- **Isolated patches are a deliberate anti-logjam tool, not a fallback.** When a
  bundle has a blocker but some components have shippable, finished improvements,
  ship the ready ones as isolated patches rather than hoarding them behind the
  blocker. Monthly-ish cadence is a healthy-flow signal, not a mandate.
- **Release tickets** — every bundle and every isolated patch is tracked as a
  Release-type work item using the templates on the Release-packing Confluence page.
  Bundle ticket flow: `Ready for dev → Working on → PR → Acceptance → Done`. Patch
  ticket flow: `Ready for dev → Working on → PR → (Acceptance) → Done` — Acceptance
  is optional for patches and is a judgment call by the dev running the patch.
- **Blocker discovery during a cut** — file with `fixVersion = current release`,
  `Priority = Blocker`, link with "blocks" to the Release ticket. Code-level rework
  happens under the new ticket's PR; the original feature ticket stays Done.

## Development Workflow

The day-to-day workflow is documented in `manifests/developer.md`. The constitution
codifies the **non-negotiable** elements of that workflow:

- Stories are pulled from the top of **Ready for dev** on the AIOT board.
- Tickets transition through: `Ready for dev → Working on → PR → Acceptance → Done`,
  driven by the dev (not the product owner).
- Scope questions surfaced during specify go back to the ticket as numbered comments;
  the ticket returns to **Planning** until resolved.
- After merge, the dev deploys/builds the dev environment and moves the ticket to
  **Acceptance** for product-owner sign-off. Rejected tickets return to **Ready for
  dev** with a comment.
- Tier and Components are owned by the product owner; devs do not modify them except
  Components when scope shifts during work.

## Component-Local: IoT Gateway (`GatewayApp`)

This section is owned by the GatewayApp repo. It extends the inherited principles
with how they apply concretely here; it MUST NOT contradict them.

### Identity and conventions

- **Component:** IoT Gateway. Repo `GatewayApp` (ADO, Smartlift project). Python 3.14
  async application running as a container (`linux/arm64`) on the Esse-ti gateway;
  merges legacy `aritco-gw-cloud-agent` (C++), `bluetooth_api` (C++), `smartlift2`
  (Python 3.6).
- **JIRA project:** `AIOT` (Aritco IoT) — one project for all four components; this
  repo's tickets carry component `IoT Gateway`. Legacy `EG` (Esse-ti Gateway) backlog
  stays on its own project/workflow until drained; new platform work is `AIOT-<id>`.
- **Branch:** `AIOT-<id>-short-description` off `dev` (never `main`/`master`).
  Legacy EG tickets keep `EG-<id>-short-description`.
- **Commit prefix:** `AIOT-<id> - <message>` (foundation style); `EG-<id> <message>`
  for legacy EG work.
- **Spec folder:** `specs/AIOT-<id>-short-description/`, committed. (`docs/superpowers/`
  stays local/ignored as before; Spec Kit artifacts do not go there.)
- **Execution:** `/speckit-implement` delegates to Superpowers
  `subagent-driven-development`; no inline implementation in the orchestrator.

### Driving-repo role (Principle II)

The Gateway rarely drives a spec. Typical flow: Backend drives the feature; this repo
gets `specs/<ticket>/ref.md` pointing at the driving spec plus its own `tasks.md`
covering only Gateway tasks. The Gateway drives when the change originates here —
lift-protocol behavior (AHL Modbus/RS485, 1000-series RS232), BLE onboarding, OTA /
container-image mechanics, or regulation forcing Gateway behavior change.

### Hardware-Aware Engineering applied (Principle VI)

Every Gateway `spec.md`/`plan.md` MUST carry a **Hardware & Field Impact** note that
answers:

1. **Backward compatibility** — deployed gateways run older images; cloud-side contract
   (device twin schema, direct-method names/payloads, telemetry shape) must stay
   readable by old and new firmware during rollout.
2. **OTA / image compatibility** — changes to the container image respect the gateway's
   legacy dockerd (classic single-manifest tar, `linux/arm64`, unique timestamp tags).
3. **Hardware test plan** — which physical rig (real lift, AHL/1000-series bench, or
   the `tests/iot-test` harness) verifies the change. `tasks.md` MUST include the
   hardware-test task and its time; estimates account for it.
4. **Safety relevance** — anything touching lift control paths is flagged explicitly.

### Graceful Degradation applied (Principle VIII)

Offline-first: lift operation and local control never depend on cloud reachability.
On connectivity loss the app keeps serving local functions, buffers what must reach
the cloud, and reconciles device twin / telemetry on reconnect. Specs for cloud-facing
features MUST state the offline behavior.

### Cross-Component Coherence applied (Principle VII)

Cloud contract changes (twin properties, DDMs, telemetry, blob transfer) are
coordinated with Backend: Backend PRs changing a contract the Gateway consumes require
Gateway-dev sign-off before merge, and vice versa.

### Tier as Presentation Gate (Principle IX)

Not applicable on the Gateway: it does not gate behavior on partner `Tier`. Tier
enforcement lives in SmartApp/SmartFleet.

### Stack guardrails

Technical conventions live in `CLAUDE.md` and `README.md` (async I/O everywhere,
error-code-name strings, `unittest` tests under `utest/`, mypy/pyright clean, Google
docstrings, simplicity over abstraction when porting legacy code). CI gate:
`utils/delivery_check.py -a -x -l -u`. `/speckit-plan`'s Constitution Check verifies
plans against this section as well as Principles I..IX.

## Governance

This constitution supersedes ad-hoc team conventions where they conflict. It does not
supersede repo-specific technical conventions (style guides, framework choices,
deployment runbooks) that operate in a different layer.

**Amendments** — changes to this constitution land via PR to this repository. The PR
description MUST justify the change and identify which version field bumps (MAJOR,
MINOR, PATCH per the rules below). Amendments require review by the dev team before
merge.

**Versioning policy** — semantic versioning applied to governance:

- **MAJOR** — backward-incompatible removal or redefinition of a principle.
- **MINOR** — new principle or section added; material expansion of existing
  guidance.
- **PATCH** — clarifications, wording, typo fixes, non-semantic refinements.

**Compliance review** — `/speckit-plan` evaluates each plan against the principles
ratified here as part of its Constitution Check gate. Violations MUST be either
removed from the plan or justified in the plan's Complexity Tracking table with a
Simpler Alternative Rejected reason. Unjustified violations block the plan.

**Runtime guidance** — for day-to-day execution detail (ticket flow steps, JIRA
templates, branch naming examples), see `manifests/developer.md`. The constitution
holds the principles; the manifest holds the practice.

**Version**: 1.0.1 | **Ratified**: 2026-05-05 | **Last Amended**: 2026-06-30
