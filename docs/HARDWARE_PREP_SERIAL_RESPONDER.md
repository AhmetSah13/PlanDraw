# Hardware Prep Serial Responder

Tam smoke prosedürü (socket vs COM vs firmware ayrımı): `docs/HARDWARE_PREP_SERIAL_SMOKE.md`

## Purpose

This document explains the development-only serial responder prepared for PlanDraw / NewBot hardware prep Stage 2.

The responder is not firmware and is not a robot controller. It exists only to let `smoke_test_serial_loopback.py` verify the host-side serial protocol against a safe virtual COM pair or non-robot serial test setup.

## Why TX-RX Echo May Not Be Enough

A simple USB-serial TX-RX echo loopback usually sends the host bytes back to the host. That proves bytes can travel through the adapter, but it does not behave like the expected MCU protocol.

`backend/scripts/smoke_test_serial_loopback.py` normal mode uses `SerialDriver`, which sends a Profile B batch:

```text
BEGIN
SPEED 1.0
PEN UP
PEN DOWN
FORWARD 0.05
END
```

After `END`, `SerialDriver` waits for:

```text
DONE
```

If a pure echo loopback only echoes `BEGIN`, `SPEED ...`, and `END`, the driver will not receive `DONE`. The likely result is timeout or unknown responses, not a valid loopback PASS.

## Responder Script

Script:

```text
backend/scripts/serial_loopback_responder.py
```

Behavior:

- Requires an explicit port argument.
- Opens no port by default.
- Must be used only with virtual COM pairs or non-robot USB-serial loopback/responder setups.
- Must not be pointed at robot, motor controller, or production firmware ports.

Supported responses:

- `BEGIN`: starts collecting a Profile B batch.
- DSL payload lines: collected until `END`.
- `END`: parses collected DSL using backend command parser; returns `DONE` if clean.
- Malformed batch: returns `ERR parse ...`.
- `STATUS`: returns `STATUS responder=1 idle=1 batches=<n>`.
- `STOP`: clears current batch and returns `DONE`.
- `--mode malformed`: forces completed batches to return `ERR forced_malformed`.

## Safe Virtual COM Setup

Use a virtual COM pair such as:

- `COM10` for the host smoke test.
- `COM11` for the responder.

The exact pair depends on the local virtual COM tool. The two ports must be paired with each other and must not be connected to a robot or motor controller.

Terminal 1, responder side:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\serial_loopback_responder.py COM11 --baudrate 115200
```

Terminal 2, host smoke test side:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\smoke_test_serial_loopback.py COM10 --baudrate 115200 --timeout 2 --mode normal
```

Expected normal result:

- Responder sees `BEGIN`.
- Responder collects DSL payload.
- Responder sees `END`.
- Responder replies `DONE`.
- Smoke test exits successfully.

## Optional Manual Checks

Malformed behavior:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\smoke_test_serial_loopback.py COM10 --baudrate 115200 --timeout 2 --mode malformed
```

Expected result:

- Responder or loopback firmware returns `ERR ...`.
- Smoke test treats expected `ERR` as success in malformed mode.

Status behavior:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\smoke_test_serial_loopback.py COM10 --baudrate 115200 --timeout 2 --mode status
```

Expected result:

- Responder returns `STATUS responder=1 idle=1 batches=<n>`.

Stop behavior:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\smoke_test_serial_loopback.py COM10 --baudrate 115200 --timeout 2 --mode stop
```

Expected result:

- Batch receives `DONE`.
- `STOP` receives `DONE`.

## Safety Rules

- Do not connect a real robot.
- Do not connect a motor controller.
- Do not change firmware.
- Do not use Bluetooth COM ports as loopback unless they are explicitly part of a proven safe virtual test setup.
- Do not use large plans.
- Do not treat this as an off-ground robot test.
- Do not proceed to Stage 3 until Stage 2 loopback has a real PASS on a safe port pair.

## Result Interpretation

Responder unit tests prove the responder state machine without hardware.

A real Stage 2 loopback PASS still requires a safe virtual COM pair or non-robot loopback setup and a successful run of:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\smoke_test_serial_loopback.py <HOST_PORT> --baudrate 115200 --timeout 2 --mode normal
```

Only after that PASS should Stage 3 off-ground hardware preparation be considered.
