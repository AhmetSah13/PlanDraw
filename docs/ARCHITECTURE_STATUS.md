# Architecture status (frozen boundaries)

This document **freezes architectural classification** for the `newbot` / PlanDraw repository. It exists so contributors do not confuse **the official product pipeline** with **experimental tooling**, **legacy copies**, or **future hardware layers**.

**Last updated:** reflects the repository as of the classification freeze.  
**Non-goals:** This file does not replace `docs/ARCHITECTURE.md` (design narrative); it is the **status map** and **boundary contract**.

---

## 1. Official core (preserve and extend)

**Definition:** The **FastAPI web backend** served as `app.api.main:app` and the modules it imports for the main request path, plus the **Vite/React** client that talks to it.

**Entrypoints**

| Entry | Location | Command / note |
|--------|-----------|----------------|
| HTTP API | `backend/app/api/main.py` | `uvicorn app.api.main:app` (from `backend/` after `pip install -e .`) |
| Web UI | `webapp/frontend/` | `npm run dev` (Vite); calls backend over HTTP |

**Frozen official pipeline (single product flow)**

```
Input → Normalize → Enrich → Path → Commands → Analyze → Optimize (optional) → Simulate (SSE) → Export
```

| Stage | Primary modules |
|--------|------------------|
| Input | `app/core/plan_module.py` (LINE), `app/normalization/normalized_plan.py` (JSON), `app/importers/dxf_importer.py`, `app/importers/dwg_converter.py` |
| Normalize | `app/normalization/plan_normalizer.py` |
| Enrich | `app/analysis/geometry_graph.py` (`enrich_plan_with_graph_metrics`) |
| Path | `app/pathing/path_generator.py` |
| Commands | `app/execution/compiler.py`, `app/execution/commands.py` |
| Analyze | `app/analysis/scenario_analysis.py` |
| Optimize | `app/pathing/path_optimizer.py` |
| Simulate | `CommandExecutor` in `app/execution/executor.py` + SSE loops in `app/api/main.py`; optional noise in `app/utils/motion_model.py` |
| Export | Same execution/analysis helpers + export handling in `app/api/main.py` |

**Supporting official modules**

- `app/api/schemas.py` — API contracts.
- `app/importers/plan_importer.py` — `NormalizedPlan` → internal `Plan` / walls / LINE text.
- `app/utils/geometry_utils.py`, `app/utils/step_size_utils.py` — helpers consumed by analysis / previews.

**Important:** `app/api/main.py` does **not** import `wall_centerline`, `wall_filter`, `graph_traversal`, or `app/robot/*`. Those are **not** part of this frozen pipeline.

---

## 2. Experimental / research (valuable, not official product path)

**Definition:** Code that is **tested and used**, but **not** on the FastAPI import/call chain for the main web product.

| Area | Items | Role |
|------|--------|------|
| Wall geometry | `app/analysis/wall_centerline.py`, `app/analysis/wall_filter.py` | DXF wall-only experiments; used from CLI scripts, not from `import_dxf` full path in `main.py`. |
| Alternate path logic | `app/pathing/graph_traversal.py` | Used by `backend/scripts/verify_dxf_drawability.py` and related reporting. |
| Mobile / alternate command text | `app/robot/mobile_mission_planner.py`, `app/robot/mobile_robot_commands.py`, `app/robot/command_generator.py` | Alternate outputs; **API does not expose** these as the primary command stream. `command_generator` is mainly covered by unit tests. |
| CLI demos | `backend/scripts/draw_plan_from_dxf.py`, `backend/scripts/verify_dxf_drawability.py` | End-to-end **CLI** flows that may combine wall processing + alternate formats. |
| Desktop pygame sim | `app/simulation/simulator.py` | **Developer / offline** tool; **not** the SSE simulation in `main.py`. Requires `pygame` (not listed in `backend/requirements.txt`). |
| Benchmarks | `benchmarks/` | External DXF sets + script-driven runs. |
| Generated reports | `backend/reports/` (if present) | Output artifacts from verification scripts, not application source. |

**Warning:** Do not assume CLI behavior matches the web API for the same DXF file (different preprocessing options may apply).

---

## 3. Legacy / deprecated (do not extend)

| Item | Status | Evidence |
|------|--------|----------|
| `webapp/backend/` | **Deprecated duplicate** | `webapp/backend/README.md` states legacy; **source of truth is `backend/`**. |

**Guidance:** Run and develop against `backend/` only. Ignore duplicate backend trees for new features.

---

## 4. Future integration (not in repo yet)

These layers are **expected** for a real floor-drawing robot but are **not** implemented as a stable interface here:

- Hardware abstraction (robot backend interface).
- Serial / ROS2 / MQTT / similar transport.
- Real differential-drive motion control (PID, yaw tracking, dynamics).
- Closed-loop localization / odometry fusion.

**Where to attach later:** After **Export** or parallel to **Command** stream, without breaking `NormalizedPlan` → path → command DSL unless deliberately versioned.

---

## 5. Current limitations (honest)

- Two **simulation** experiences exist: **SSE + executor** (web) vs **pygame** (offline). Only the former is the official product path.
- Two **command “styles”** exist in the repo: web pipeline uses the **DSL** produced by `compile_path_to_commands` / `serialize_commands`; CLI scripts may emit **other** text formats (`PEN_UP`/`DRAW`, mobile `MOVE_TO`/`DRAW_TO`). They are **not** unified as one API output today.
- **DXF import** in the API does **not** run the full wall-centerline + graph-traversal stack used by some CLI verification flows.

---

## 6. Immediate next steps (documentation-first)

1. Treat **`docs/ARCHITECTURE_STATUS.md`** as the boundary reference before any refactor.
2. When adding features, state whether they target **Official core** or **Experimental** (new scripts / subpackages).
3. Before moving code between folders: re-read this file and update the **module lists** in section 1–2.
4. **Regression guard:** HTTP golden path for the official API — `backend/tests/test_official_core_golden_path.py` (`import_plan` → `analyze`; optional `export`). Requires `httpx` (Starlette `TestClient`).

---

## 7. Related documents

- `docs/ARCHITECTURE.md` — Design narrative and pipeline diagram.
- `docs/DRIVERS.md` — Driver boundary (`List[Command]`), `NullDriver`, future adapters.
- `README.md` (repo root) — How to run backend/frontend and demo scripts.
- `backend/README.md` — Backend layout and tests.
