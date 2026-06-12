# az one-liners — manual DDM poking

Replace `$HUB` / `$DEV` (PowerShell: `$HUB="..."; $DEV="GW-dev-test2"`).

```powershell
# reads
az iot hub invoke-device-method --hub-name $HUB --device-id $DEV --method-name la.read.lift-type --method-payload '{}'
az iot hub invoke-device-method --hub-name $HUB --device-id $DEV --method-name la.read.ar-number --method-payload '{}'
az iot hub invoke-device-method --hub-name $HUB --device-id $DEV --method-name la.read.parameter --method-payload '{\"parameter\": 1}'
az iot hub invoke-device-method --hub-name $HUB --device-id $DEV --method-name la.read.parameters --method-payload '{\"parameters\": [1, 2, 3]}'
az iot hub invoke-device-method --hub-name $HUB --device-id $DEV --method-name la.read.parameters --method-payload '{\"from\": 1, \"to\": 5}'

# writes (bench!)
az iot hub invoke-device-method --hub-name $HUB --device-id $DEV --method-name la.write.parameter --method-payload '{\"parameter\": 1, \"value\": \"7\"}'
az iot hub invoke-device-method --hub-name $HUB --device-id $DEV --method-name la.write.read.parameter --method-payload '{\"parameter\": 1, \"value\": \"7\"}'
az iot hub invoke-device-method --hub-name $HUB --device-id $DEV --method-name la.write.ar-number --method-payload '{\"value\": \"AR563412\"}'

# download — happy path needs a real SAS URL on an allowlisted host.
# Mint one by running tests/test_blob_integration.py (steps 1-6 upload a
# fixture and build the SAS URL), then:
az iot hub invoke-device-method --hub-name $HUB --device-id $DEV --method-name ca.download-file --method-payload '{\"uri\": \"<SAS-URL>\", \"type\": \"0x0B\"}'
# NOTE: never paste SAS URLs into logs/tickets — they are credentials.

# twin
az iot hub device-twin show --hub-name $HUB --device-id $DEV
az iot hub device-twin update --hub-name $HUB --device-id $DEV --desired '{\"downloadMaxBytes\": 1048576}'

# telemetry (bounded window; use the dedicated consumer group)
az iot hub monitor-events --hub-name $HUB --device-id $DEV --consumer-group nhGwTest --timeout 30 --props all
```
