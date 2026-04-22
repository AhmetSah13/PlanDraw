# Driver layer (hardware abstraction)

## Official boundary

The intended interface for future real-robot execution is **`List[Command]`** from `app.execution.commands` (dataclasses: `SpeedCommand`, `PenCommand`, `MoveCommand`, etc.).

- **Text DSL** (`serialize_commands`) and **export formats** (`export_commands_to_string`: `robot_v1`, `gcode_lite`, …) are **derived views** of the same list.
- Drivers should **consume `List[Command]`** as the primary input, not raw export text, so format changes do not break hardware integration.
- That canonical boundary stays **`List[Command]`** even for serial: the host serializes to wire bytes **inside** the driver (e.g. DSL text), so compiler/export strings are not the primary contract to hardware.

## SerialDriverStub (dry-run)

`app.drivers.serial_driver_stub.SerialDriverStub` implements `RobotDriver` but performs **no real serial I/O** (no `pyserial`). It builds the first agreed wire payload from `serialize_commands` (UTF-8), stores `last_payload_text` / `last_payload_bytes` for tests, and exposes port/baud/wire_format in `get_status` as placeholders for a future real driver.

**Future work:** real transport, optional ACK protocol, and line/batch framing — not in the stub batch.

Host ↔ MCU wire contract (v1): **`docs/SERIAL_PROTOCOL_V1.md`**.

## SerialDriver (pyserial)

`app.drivers.serial_driver.SerialDriver` uses **`pyserial`** and the helpers in **`app.drivers.serial_protocol`** (`serialize_commands` → `frame_dsl_payload` → `wire_text_to_bytes`, `parse_response_line`, `frame_stop_line`) as described in **`docs/SERIAL_PROTOCOL_V1.md`**.

- Default **profile B** (`BEGIN`/`END` batch) and **`expect_done_after_batch=True`**: after `send_commands`, the driver reads until **`DONE`** or **`ERR`** (OK/STATUS/unknown lines are skipped until then).
- **Real MCU firmware** implementing the same line protocol is still required; this is only host-side I/O.
- **Unit tests** inject a fake `serial_connection` and do **not** require physical hardware.
- If **`pyserial`** is not installed and no connection is injected, **`connect()`** raises **`ImportError`**.
- MCU firmware design (parser, state machine, responses): **`docs/FIRMWARE_ARCHITECTURE_V1.md`**.

## Protocol

`app.drivers.base.RobotDriver` defines the minimal protocol: `connect`, `disconnect`, `stop`, `get_status`, `send_commands`.

## NullDriver

`app.drivers.null_driver.NullDriver` is the first non-hardware implementation: it stores the last command list and optional serialized DSL for debugging. No I/O.

## FileDriver

`app.drivers.file_driver.FileDriver` writes the same `List[Command]` to a **filesystem path** (still no robot hardware). It reuses existing rendering:

- **`dsl` (default):** `serialize_commands` — canonical DSL text, same family as in-memory `NullDriver` serialization, deterministic body.
- **`robot_v1`:** `export_commands_to_string(..., format="robot_v1")` — same export pipeline as analysis/API-style robot files (includes headers and stats).

`get_status()` includes `connected`, `driver_name` (`"file"`), `last_command_count`, `output_path`, `output_mode`, `last_write_succeeded`, and `last_error` (on I/O failure). Write failures are recorded in status and do not raise from `send_commands`.

## Dispatch helper

`app.execution.driver_dispatch.dispatch_commands` takes `List[Command]` and an optional `RobotDriver`. If `driver` is `None`, it is a no-op. Otherwise it runs `connect` → `send_commands` → `disconnect` (in `finally` after a successful `connect`).

- **HTTP job (ince kablo):** `POST /api/jobs` gövdesinde `file_artifact.enabled: true` ise, simülasyonda kullanılan **aynı** `List[Command]` ile `done` SSE olayından önce `FileDriver` + `dispatch_commands` çağrılır; yol `JOB_FILE_ARTIFACT_ROOT` (varsayılan `backend/out/job_artifacts/`) altında `{job_id}.dsl.txt` veya `.robot_v1.txt`. `done` payload içinde `file_artifact` özeti döner.
- Diğer sürücüler (Serial vb.) hâlâ FastAPI’ye bağlı değildir.
- **Separate from simulation** (`CommandExecutor` / SSE) and from **export** (`export_commands_to_string`): dispatch is for optional physical or test driver handoff, not for string generation.

## Motion execution + optional dispatch (bridge)

`app.motion.motion_dispatch_bridge.execute_and_optionally_dispatch` runs the **new motion simulation path** first (`execute_command_sequence_motion`), then optionally forwards the **same** `List[Command]` through `dispatch_commands` when `dispatch_enabled` and a `RobotDriver` are provided.

- **Dev/test architecture only** — not wired to FastAPI; does not replace `CommandExecutor` or export.
- **Dispatch errors** are captured in the combined result (`dispatch_error`); they do not replace or invalidate the motion outcome in this first version.
- Integration coverage: `tests/test_motion_dispatch_bridge_file_integration.py` exercises `execute_and_optionally_dispatch` with `FileDriver` (artifact on disk, `driver_status` checks).

## Future adapters

Serial, ROS 2, file sink, etc. can implement the same protocol later. A richer status contract (e.g. `DriverResult`) may be added without changing the command model.
