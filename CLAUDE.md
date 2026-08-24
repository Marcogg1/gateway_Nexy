# CLAUDE.md

## Project Overview

**GatewayApp** is a Python 3.14 gateway application for Aritco lift systems. It merges functionality from three legacy repositories:
- `aritco-gw-cloud-agent` (C++ cloud agent)
- `bluetooth_api` (C++ Bluetooth controller)
- `smartlift2` (Python 3.6 lift agent)

The gateway connects lift equipment to Azure IoT Hub for cloud monitoring and management.

## Commands

```bash
pytest utest/                        # Run all tests (preferred)
python -m mypy .                     # Type check — run before every commit/PR (CI runs it)
pip install -r requirements_host.txt # Dev dependencies
```

CI runs `utils/delivery_check.py -a -x -l -u` via Azure Pipelines.

## Branching, commits, PRs

- **Main branch**: `dev` (not `main` or `master`)
- **Feature branches**: `AIOT-<id>-short-description` (AIoT platform work, JIRA project AIOT). Legacy Esse-ti Gateway tickets: `EG-XX-description`.
- Commit messages: `AIOT-<id> - Short imperative description` (foundation style). Legacy EG work: `EG-XX Short imperative description` (no dash; match history). Keep formatting/whitespace-only changes in their own commit.
- PRs: `az repos pr create --repository GatewayApp --target-branch dev` (Azure DevOps, not `gh`); description = Summary bullets only.

## Design Principles

### Simplicity over abstraction
When implementing features based on old C++/Python 3.6 code:
1. Match the old function signature and return type
2. Use simple, direct implementations - avoid overengineering
3. Return `None` if old code returned `void`
4. Return error code strings if old code used error codes
5. Don't add complex result objects unless necessary

### Error handling pattern
Handlers return error-code **name strings** (`self.ErrorCode.NO_ERR.name`), not exceptions or result objects — legacy contract. Each handler has its own enum in `src/lib/error_signals.py` (rule `.claude/rules/error-signals.md` loads with it). New async functions return `None` to match the old C++ fire-and-forget pattern.

## Coding Standards

- **Google docstrings** for all functions and classes
- Type hints required: use `str | None` not `Optional[str]`
- All I/O operations use async/await
- Callbacks/hooks invoked from async loops use `async def` even if body is sync — prevents blocking when impl grows I/O
- Logging: `from lib.logging_config import setup_logging, get_logger` — never `import logging` directly
- File-scoped conventions live in `.claude/rules/` (tests, parameter tables, vendor/typings, AUDIT_BACKLOG) and load only when the matching file is opened

## AIoT Spec Kit operational instructions

This repo follows the AIoT platform's Spec Kit setup. Canonical sources (do not restate here):
constitution → `.specify/memory/constitution.md` (inherits **AIoTDevFoundations** v1.0.1;
Gateway-local section at the end), day-to-day workflow → `AIoTDevFoundations/manifests/developer.md`.
Read the constitution before non-trivial spec work. Re-sync with
`AIoTDevFoundations/manifests/spec-kit-conform.md` when the foundation moves.

### Pipeline and conventions

- Pipeline: `/speckit-specify <ticket>` → (`/speckit-clarify`) → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`.
- `/speckit-implement` **delegates** to Superpowers `subagent-driven-development` — never implement tasks inline.
- JIRA project: `AIOT` (Aritco IoT, component `IoT Gateway`) — same project as Backend/SmartFleet/SmartApp. Legacy `EG` (Esse-ti Gateway) tickets stay on their own project until drained.
- Branch: `AIOT-<id>-short-description` off `dev` (legacy: `EG-<id>-…`). When running `/speckit-specify`, set BOTH `GIT_BRANCH_NAME=AIOT-<id>-short-description` (branch) and `SPECIFY_FEATURE_DIRECTORY=specs/AIOT-<id>-short-description` (spec dir) — otherwise the scripts fall back to sequential `NNN-` numbering for either.
- Spec folder: `specs/AIOT-<id>-short-description/` (same short name as the branch), committed.
- Commit prefix: `AIOT-<id> - <message>` via ticket-commit (legacy EG: `EG-<id> <message>`). The Spec Kit `after_*` hooks (`/speckit-git-commit`) are **disabled** (`auto_commit: false` for every event in `.specify/extensions/git/git-config.yml`) and make no commits — **ticket-commit owns all commits**. Keep auto-commit off: its `[Spec Kit] …` messages would violate the prefix rule.
- Driving-repo role: Gateway usually **consumes** Backend-driven specs → `specs/<ticket>/ref.md` pointing at the driving repo + own `tasks.md` with Gateway-only tasks. Gateway drives only Gateway-originated changes.
- Every spec/plan carries a **Hardware & Field Impact** note (backward compat with deployed firmware, OTA/image compat, hardware-test plan + time, safety relevance) — constitution Principle VI.

### JIRA round-trip via Atlassian MCP

**Prerequisite check.** Before proposing any JIRA action, confirm the Atlassian MCP is connected (e.g. list accessible Atlassian resources). If not connected, stop and tell the dev: "Atlassian MCP is required for AIoT spec work — please configure it before continuing." Missing MCP is a blocker, not something to work around manually.

**When `/speckit-specify` or `/speckit-clarify` surfaces unresolved questions for the product owner:**

1. Draft a numbered comment with the questions (format below).
2. Show the dev the proposed comment and the proposed transition (`Working on` or `Ready for dev` → **Planning**).
3. Ask for explicit confirmation. Do NOT post or transition until the dev approves.
4. On approval, post via `addCommentToJiraIssue` and transition via `transitionJiraIssue`.
5. Confirm to the dev what was posted and the ticket's new status, with the JIRA URL.

Comment format:

```
Questions from the spec process:
1. <question>
2. <question>
3. <question>
```

**When the product owner answers** and the ticket is back at **Ready for dev**, re-read the JIRA comments via `getJiraIssue` (include comments in the field list), update the spec accordingly, then run `/speckit-plan` and `/speckit-tasks`.

**Hard rule:** the agent never posts comments or transitions tickets without explicit dev confirmation. Automation runs through the dev, not around them.
