---
paths:
  - "utest/**"
---

Tests use `unittest` with `setUp`/`tearDown` (not pytest fixtures); run with `pytest utest/`.
Don't hardcode counts that break when data tables grow (assert on membership/ranges instead).
Run `python -m mypy .` from the repo root before committing — CI runs it.
