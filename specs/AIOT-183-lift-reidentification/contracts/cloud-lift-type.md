# Contract: lift-type surfaces exposed to the cloud

Scope: the three places the gateway tells the cloud which lift is attached. **No field names, method names or payload shapes change.** What changes is *when* values are emitted and that `"unknown"` is now actually reported.

## 1. Reported twin property `gw.liftType`

```json
{ "gw": { "liftType": "unknown" | "AHL" | "1k" } }
```

| Before AIOT-183 | After AIOT-183 |
|---|---|
| Reported once at startup **only if identified**; on UNKNOWN the property is not written → cloud keeps whatever the previous boot reported | Reported once at startup with the current value (`"unknown"` when unidentified), and again with the real type when background identification succeeds |

Consumers (Backend, SmartFleet): must accept `"unknown"` as a valid value and must treat a change from `"unknown"` to a concrete type as normal (not a device replacement). Numeric-code migration (`"0"/"1"/"2"`) is tracked in EG-71 and out of scope here.

## 2. Telemetry message custom property `LIFT_TYPE`

Set on every `send_event` message: `message.custom_properties["LIFT_TYPE"] = "unknown" | "AHL" | "1k"`.

| Before | After |
|---|---|
| Constant for the process lifetime (snapshot at startup) | May change once, from `"unknown"` to the identified type, at the moment of late identification. Heartbeats sent while unknown carry `"unknown"`. |

## 3. Direct method `la.read.lift-type`

Response `{"ts": <unix>, "lt": "0" | "1" | "2"}` (0 = unknown, 1 = AHL, 2 = 1k). **Unchanged** — already reads the live proxy state, so it reflects late identification automatically.

## 4. Lift DDMs while unknown

Unchanged: every lift-touching direct method returns the existing INIT_ERR envelope (`errorSource: "LiftProxy"`, `errorCode: "INIT_ERR"`) until identification succeeds, then works normally. No new error codes.

## Compatibility statement

Older gateway images never emit `"unknown"` for `gw.liftType` (they omit the field) and never change `LIFT_TYPE` mid-session. Both behaviours are supersets of the old ones; no consumer that tolerates the old behaviour needs a change, but Backend dev sign-off is requested in the PR per constitution Principle VII.
