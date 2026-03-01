# NewBot Architecture Overview

## 1. Problem Statement

NewBot aims to bridge human-prepared construction plans and on-site robotic execution:

- **Human-authored plans** — Plans are created by humans (as drawings, CAD, or structured data) and describe what should be drawn (walls, lines, contours).
- **Robot execution on-site** — A robot interprets these plans and draws them automatically in the real world (e.g. on floor, whiteboard, or material).
- **Software core** — The core is **hardware-agnostic**: it produces a validated path and command stream. Actual hardware (pen plotter, gantry, mobile robot) is integrated via export formats and optional drivers.
- **Safety and extensibility** — The pipeline includes dry-run analysis, collision checks, and time estimates so unsafe scenarios can be blocked before export or execution. The design allows plugging in new import sources (DXF, PDF, image) and new exporters or robot backends without changing the core.

## 2. High-Level Pipeline

The full flow from plan input to simulation and export:

**JSON / CAD / Plan Input**  
→ **Import** (validation, optional normalization)  
→ **NormalizedPlan** (segment-based, units and scale)  
→ **Plan (internal LINE-based)**  
→ **Path Generation** (discretized points)  
→ **Command Compilation** (SPEED, PEN, MOVE, …)  
→ **Analysis** (safety gate: bounds, collisions, time)  
→ **Simulation** (optional noise/drift)  
→ **Export** (ROBOT_V1 / G-code-like)

ASCII diagram:

```
[ JSON Plan / LINE text ]
         |
         v
[ Import & Validate ]
         |
         v
[ NormalizedPlan ]  (optional: normalize → merge/simplify)
         |
         v
[ Plan (Walls) ]    (internal LINE / wall list)
         |
         v
[ PathGenerator ]   (step_size → point list)
         |
         v
[ Commands ]        (SPEED, PEN, MOVE, TURN, …)
         |
         +----------> Analyze   (dry-run, bounds, collisions, time)
         |
         +----------> Simulate  (tick-based, optional drift/noise)
         |
         +----------> Export    (ROBOT_V1, gcode_lite)
```

## Module Map (backend/app)

Modüler yapıda her paketin sorumluluğu:

| Paket | Açıklama |
|-------|----------|
| **app/core** | Paylaşılan alan modelleri: `Plan`, `Wall` (plan_module). Plan metninden/dosyadan yükleme. |
| **app/importers** | Dış kaynaklardan plan: `dxf_importer` (DXF → NormalizedPlan, katman önizleme), `dwg_converter` (DWG→DXF), `plan_importer` (NormalizedPlan → Plan, walls, plan text). |
| **app/normalization** | `normalized_plan`: NormalizedPlan şeması, JSON import. `plan_normalizer`: segment birleştirme, recenter, segment_budget. |
| **app/pathing** | `path_generator`: segment sıralama (nearest-neighbor), nokta üretimi (ceil + eşit bölme). `path_optimizer`: komut sadeleştirme (collinear, RDP). |
| **app/analysis** | `scenario_analysis`: dry-run analiz, bounds/collision/move limitleri, istatistikler, export_commands_to_string. |
| **app/simulation** | `simulator`: tick tabanlı simülasyon, pygame/export (opsiyonel). |
| **app/execution** | `commands`: komut parse/serialize (SPEED, PEN, MOVE, REPEAT, …). `compiler`: path → komut listesi. `executor`: komut adım adım ilerletme. |
| **app/utils** | `step_size_utils`: bbox-adaptif recommended_step_size. `geometry_utils`: segment kesişim, mesafe. `motion_model`: drift/noise. |
| **app/api** | FastAPI `main`: endpoint’ler (import_dxf, import_dwg, import_plan, analyze, simulate, compile, export). `schemas`: Pydantic modelleri. |

## End-to-End Pipeline (özet)

```
  [ DXF/DWG/JSON ]
         |
         v
  [ Import ]  (dxf_importer, plan_importer, import_plan)
         |
         v
  [ NormalizedPlan ]  -----> [ Preview (layers, recommended_step_size) ]
         |
         v
  [ Normalize ]  (plan_normalizer: merge, recenter, segment_budget)
         |
         v
  [ Plan (Walls) ]  (normalized_to_plan)
         |
         v
  [ Path ]  (path_generator: order_walls, step_size → points)
         |
         v
  [ Commands ]  (compiler: SPEED, PEN, MOVE…)
         |
         +----------> [ Analyze ]  (bounds, collisions, time) ----> BLOCKED / SAFE
         |
         +----------> [ Simulate ]  (tick, optional drift/noise)
         |
         +----------> [ Export ]  (ROBOT_V1, gcode_lite)
```

## How to run tests

- **backend/ içinden (önerilen):**  
  `cd backend` → `pip install -r requirements.txt` → `pip install -e .` → `pytest tests` veya `python -m unittest discover -s tests -p "test_*.py" -v`
- **Repo kökünden:**  
  `pip install -e backend` (bir kez) → `pytest backend/tests` veya `python -m pytest backend/tests`  
  Pytest kullanılıyorsa `backend/tests/conftest.py` sayesinde editable install olmadan da `backend` sys.path’e eklenir.
- FastAPI/pydantic gerektiren testler için sanal ortamda `requirements.txt` yüklü olmalı.

## 3. NormalizedPlan Concept

- **Why it exists** — Different sources (JSON, future DXF/PDF/image) describe the same logical “plan” in different formats. NormalizedPlan is a single, validated representation the rest of the pipeline consumes. It decouples “how the plan was authored” from “how we generate path and commands.”
- **Hardware-agnostic** — NormalizedPlan is geometric only: segments, units, scale, origin. It says *what* to draw, not *how* (no motor speeds or hardware commands). Speed and step size are applied later during path generation and command compilation, so the same plan can target different robots or export formats.
- **Contents today** — Segments (each with x1, y1, x2, y2; optional thickness), units (e.g. mm, cm, m), scale factor, origin, and optional metadata. Empty segment lists are rejected at import.
- **Future importers** — Any importer (DXF, PDF, image extractor) can plug in by producing this same NormalizedPlan (or a JSON payload that validates to it). The rest of the pipeline (path → commands → analyze → simulate → export) stays unchanged.

## 4. Import Options

- **Endpoint** — `POST /api/import_plan`. Request body is JSON (NormalizedPlan-shaped: segments, units, scale, origin, etc.).
- **normalize** — When true, the server applies normalization (e.g. merge collinear segments, drop zero-length, merge endpoints within tolerance). Response can include warnings from this step.
- **return_plan_text** — If true, response includes LINE-format plan text (one LINE x1 y1 x2 y2 per segment) so the UI can show or edit it.
- **return_commands_text** — If true, response includes the compiled command script (SPEED, PEN, MOVE, …) so W1/W2 can use it immediately.
- **return_raw_path** — If true, response includes the discretized path points (raw_path_points) for preview or downstream use.
- **step_size** — Distance between path points used when generating path and commands_text.
- **speed** — Default robot speed used when compiling commands_text.

Errors are returned with HTTP 200, `ok: false`, and an `error` message; validation failures (e.g. empty segments) use the same convention.

## 5. Safety & Analysis Layer

Before execution or export, the pipeline supports a **dry-run** analysis step:

- **Bounds** — The path is checked against optional world limits; out-of-bounds moves can be reported or block export.
- **Time estimation** — Total duration is estimated from path length and speeds for planning and UX.
- **Collision detection** — The tool path is checked against walls (and optionally obstacles). Collisions can be classified (e.g. touch, proper overlap) and reported; when configured in “error” mode, unsafe scenarios **block** export or simulation.
- **Why block** — Blocking prevents generating files or sending commands that would cause the robot to draw through walls or violate safety constraints. The UI can show diagnostics and let the user fix the plan or script before re-analyzing.

## 6. Frontend Integration

- **W3 Plan** — LINE editor for direct plan text (LINE x1 y1 x2 y2) and **JSON import**: file input or “Örnek JSON yükle.” Import calls `/api/import_plan` and, on success, fills plan text, script, walls, and raw path so the app is ready for W1/W2 and Export without a separate “Generate Script” step. Existing “Generate Script” (compile_plan) still works for LINE-only flow.
- **W1 Analyze** — Runs analysis on the current script (dry-run, bounds, collisions, time). Used after import or after compiling from plan text.
- **W2 Simulate / Draw** — Tick-based simulation and live draw using the same script and walls; optional motion noise/drift for realism.
- **Export** — ROBOT_V1 or gcode_lite format from the current script and start position; blocked if analysis marks the scenario unsafe (when configured to block).

## 7. Extensibility Roadmap (Short)

- **DXF importer** — Parse DXF entities into segments and produce NormalizedPlan (or equivalent JSON) for `/api/import_plan`.
- **PDF / Image extractor** — Extract lines or contours from PDF or raster images and feed the same pipeline.
- **Sensor feedback / closed-loop** — Use real-world feedback (e.g. position, obstacles) to adjust or pause execution; analysis layer can be extended to support “safe to proceed” checks.
- **ROS / real robot integration** — Publish path or commands to ROS; drive real hardware with the same validated command stream used in simulation and export.
