---
paths:
  - "src/lib/error_signals.py"
---

One `@unique class XxxCode(Enum)` per handler, each with a `SOURCE` attribute used for cloud error
tracking (`errorSource`). Handlers return error-code *name strings* (e.g. `MbCode.NO_ERR.name`), not
exceptions or result objects — legacy C++/Python-3.6 contract. Add codes to the owning handler's
enum; never rename existing members (cloud tooling matches on names).

```python
def validate_input(self, args: list) -> str:
    if invalid:
        return self.ErrorCode.ARGS_IN_LEN_ERR.name
    return self.ErrorCode.NO_ERR.name
```
