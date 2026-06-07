# Hardware Prep Socket Loopback

## Purpose

Socket loopback provides a driver-free way to validate the serial protocol flow without COM ports, Windows driver changes, firmware, robot hardware, or motor controllers.

It is intended for PlanDraw / NewBot hardware prep when virtual COM drivers are unavailable or not desired.

## Why Socket Loopback

The normal serial smoke test expects protocol responses such as `DONE`, `ERR`, and `STATUS`. A pure TX-RX echo loopback may only echo bytes and may not produce these protocol responses.

Socket loopback replaces the physical serial transport with localhost TCP:

- Host side: `SocketDriver`
- Responder side: `socket_loopback_responder.py`
- Transport: `127.0.0.1:9000`
- Protocol: same line-based `BEGIN`, payload, `END`, `DONE`, `ERR`, `STATUS`, `STOP` behavior

No real COM port is opened.

## Files

- Driver: `backend/app/drivers/socket_driver.py`
- Responder: `backend/scripts/socket_loopback_responder.py`
- Smoke test extension: `backend/scripts/smoke_test_serial_loopback.py --driver socket`
- Tests: `backend/tests/test_socket_driver.py`

## How To Run

Terminal 1, start responder:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\socket_loopback_responder.py
```

Terminal 2, normal mode:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\smoke_test_serial_loopback.py --driver socket
```

Optional modes:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\smoke_test_serial_loopback.py --driver socket --mode status
```

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\smoke_test_serial_loopback.py --driver socket --mode malformed
```

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\smoke_test_serial_loopback.py --driver socket --mode stop
```

Custom port:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\socket_loopback_responder.py --host 127.0.0.1 --port 9001
```

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\smoke_test_serial_loopback.py --driver socket --host 127.0.0.1 --port 9001
```

## Expected Results

normal:

- Host sends `BEGIN`, DSL payload, `END`.
- Responder returns `DONE`.
- Smoke test exits successfully.

status:

- Host sends `STATUS`.
- Responder returns `STATUS responder=1 idle=1 batches=<n>`.

malformed:

- Host sends malformed batch.
- Responder returns `ERR parse ...`.
- Smoke test treats expected `ERR` as success.

stop:

- Host sends valid batch and receives `DONE`.
- Host sends `STOP`.
- Responder returns `DONE`.

## Safety Notes

- No robot is used.
- No motor controller is used.
- No firmware is changed.
- No COM port is opened.
- No Windows driver is installed.
- No `dry_run=false` hardware path is used.
- This validates protocol transport behavior only; it is not an off-ground hardware test.

## Next Step

After socket loopback passes, a real virtual COM or safe non-robot serial loopback can still be used if desired. Stage 3 should remain blocked until the team intentionally chooses to proceed to off-ground physical safety testing.
