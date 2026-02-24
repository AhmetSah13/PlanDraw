import React, { useCallback, useMemo, useRef, useState, useEffect } from "react";
import { analyzeScenario, createJob, getJobStream, stopJob, compilePlan, exportRobot } from "./api.js";

const DEFAULT_SCRIPT = `# name: quick_test
# units: WORLD
SPEED 120
PEN DOWN
REPEAT 4
  FORWARD 100
  TURN 90
END
PEN UP
`;

const PLAN_STORAGE_KEY = "plandraw_plans_v1";

const DEFAULT_PLAN = `# square room
LINE 0 0 200 0
LINE 200 0 200 200
LINE 200 200 0 200
LINE 0 200 0 0
`;

const L_CORRIDOR_PLAN = `# L corridor
LINE 0 0 150 0
LINE 150 0 150 80
LINE 150 80 250 80
LINE 250 80 250 200
LINE 250 200 0 200
LINE 0 200 0 0
`;

const DEFAULT_TEMPLATES = [
  { id: "template-square", name: "Square room", plan_text: DEFAULT_PLAN, options: { step_size: 5, speed: 120, world_scale: 1, world_offset: [0, 0] }, updated_at: new Date().toISOString() },
  { id: "template-l", name: "L corridor", plan_text: L_CORRIDOR_PLAN, options: { step_size: 5, speed: 120, world_scale: 1, world_offset: [0, 0] }, updated_at: new Date().toISOString() }
];

function Badge({ ok, text }) {
  const style = {
    display: "inline-block",
    padding: "4px 10px",
    borderRadius: 999,
    fontSize: 12,
    border: "1px solid #333",
    background: ok ? "#103d25" : "#3d1010",
    color: "#fff",
    marginLeft: 8
  };
  return <span style={style}>{text}</span>;
}

function DiagList({ title, items }) {
  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ fontWeight: 700, marginBottom: 6 }}>{title}</div>
      <div style={{ maxHeight: 220, overflow: "auto", border: "1px solid #333", borderRadius: 8, padding: 8 }}>
        {items.length === 0 ? (
          <div style={{ opacity: 0.7 }}>Yok</div>
        ) : (
          items.map((d, idx) => (
            <div key={idx} style={{ marginBottom: 8 }}>
              <div>
                <b>{d.severity}</b> line {d.line}: {d.message}
              </div>
              {d.text ? <div style={{ opacity: 0.8, fontFamily: "monospace" }}>{d.text}</div> : null}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

const MARGIN = 40;
const MIN_SCALE = 0.05;
const MAX_SCALE = 200;

function computeFitView(bounds, canvasW, canvasH, margin = 40) {
  if (!bounds || bounds.length !== 4) {
    return { scale: 1, offsetX: canvasW / 2, offsetY: canvasH / 2 };
  }
  let [minx, miny, maxx, maxy] = bounds;
  if (maxx - minx < 1e-9) maxx = minx + 1;
  if (maxy - miny < 1e-9) maxy = miny + 1;
  const scale = Math.min(
    (canvasW - 2 * margin) / (maxx - minx),
    (canvasH - 2 * margin) / (maxy - miny)
  );
  const centerWorldX = (minx + maxx) / 2;
  const centerWorldY = (miny + maxy) / 2;
  const centerScreenX = canvasW / 2;
  const centerScreenY = canvasH / 2;
  const offsetX = centerScreenX - centerWorldX * scale;
  const offsetY = centerScreenY + centerWorldY * scale;
  return { scale, offsetX, offsetY };
}

function resetView(canvasW, canvasH) {
  return { scale: 1, offsetX: canvasW / 2, offsetY: canvasH / 2 };
}

function formatSecondsShort(value) {
  if (value == null) return "—";
  const v = Number(value);
  if (!Number.isFinite(v)) return "—";
  return `${v.toFixed(1)} s`;
}

function formatNumberCompact(value, maxFraction = 2) {
  if (value == null) return "—";
  const v = Number(value);
  if (!Number.isFinite(v)) return "—";
  if (Math.abs(v) >= 1000) return v.toFixed(0);
  if (Math.abs(v) >= 100) return v.toFixed(1);
  return v.toFixed(maxFraction);
}

function formatBoundsHuman(bounds) {
  if (!bounds || bounds.length !== 4) return "—";
  const [minx, miny, maxx, maxy] = bounds;
  const width = maxx - minx;
  const height = maxy - miny;
  return `${formatNumberCompact(width, 1)} × ${formatNumberCompact(height, 1)}`;
}

function StatusBadgeLarge({ blocked }) {
  const ok = !blocked;
  const bg = ok ? "#022c22" : "#3b0a0a";
  const border = ok ? "#16a34a" : "#f97373";
  const color = ok ? "#bbf7d0" : "#fecaca";
  const label = ok ? "✅ SAFE" : "⛔ BLOCKED";
  const desc = ok ? "Senaryo çalıştırılabilir." : "Hata var. Çalıştırma önerilmez.";
  return (
    <div style={{ textAlign: "center" }}>
      <div
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "8px 18px",
          borderRadius: 999,
          border: `1px solid ${border}`,
          background: bg,
          color,
          fontWeight: 800,
          fontSize: 16,
          letterSpacing: 0.4
        }}
      >
        {label}
      </div>
      <div style={{ marginTop: 8, fontSize: 13, opacity: 0.85 }}>{desc}</div>
    </div>
  );
}

function Accordion({ title, subtitle, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div
      style={{
        border: "1px solid #333",
        borderRadius: 12,
        padding: 12,
        background: "#151515",
        boxShadow: "0 10px 25px rgba(0,0,0,0.45)"
      }}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 8,
          background: "transparent",
          border: "none",
          padding: 0,
          color: "#eee",
          cursor: "pointer"
        }}
      >
        <div>
          <div style={{ fontWeight: 800, fontSize: 14 }}>{title}</div>
          {subtitle ? <div style={{ fontSize: 11, opacity: 0.7, marginTop: 2 }}>{subtitle}</div> : null}
        </div>
        <span style={{ fontSize: 16 }}>{open ? "▾" : "▸"}</span>
      </button>
      {open && <div style={{ marginTop: 10, fontSize: 12 }}>{children}</div>}
    </div>
  );
}

export default function App() {
  const [script, setScript] = useState(DEFAULT_SCRIPT);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [activeTab, setActiveTab] = useState("w1");

  const [simRunning, setSimRunning] = useState(false);
  const simAbortRef = useRef(null);
  const [speedMultiplier, setSpeedMultiplier] = useState(1.0);
  const [tickState, setTickState] = useState(null);
  const traceRef = useRef([]);
  const canvasRef = useRef(null);
  const boundsRef = useRef(null);
  const viewRef = useRef(resetView(600, 400));
  const tickStateRef = useRef(null);
  const panStartRef = useRef(null);
  const skippedClickRef = useRef(false);
  const jobIdRef = useRef(null);
  const [simulateError, setSimulateError] = useState("");
  const [blockedSim, setBlockedSim] = useState(null);
  const queueRef = useRef([]);
  const rafIdRef = useRef(null);

  const [planText, setPlanText] = useState(DEFAULT_PLAN);
  const [stepSize, setStepSize] = useState(5);
  const [planSpeed, setPlanSpeed] = useState(120);
  const [worldScale, setWorldScale] = useState(1);
  const [worldOffsetX, setWorldOffsetX] = useState(0);
  const [worldOffsetY, setWorldOffsetY] = useState(0);
  const [compileBusy, setCompileBusy] = useState(false);
  const [compileError, setCompileError] = useState("");
  const [generatedScript, setGeneratedScript] = useState("");
  const [planList, setPlanList] = useState(() => {
    try {
      const raw = localStorage.getItem(PLAN_STORAGE_KEY);
      if (!raw) return DEFAULT_TEMPLATES;
      const list = JSON.parse(raw);
      return Array.isArray(list) && list.length > 0 ? list : DEFAULT_TEMPLATES;
    } catch {
      return DEFAULT_TEMPLATES;
    }
  });
  const [selectedPlanId, setSelectedPlanId] = useState("");
  const [planName, setPlanName] = useState("");

  const [walls, setWalls] = useState([]);
  const [rawPath, setRawPath] = useState([]);
  const [showWalls, setShowWalls] = useState(true);
  const [showPathPreview, setShowPathPreview] = useState(true);
  const [showGhostPath, setShowGhostPath] = useState(true);
  const [showCollisions, setShowCollisions] = useState(true);
  const [collisionCount, setCollisionCount] = useState(0);
  const [collisionsSample, setCollisionsSample] = useState([]);
  const [startPoint, setStartPoint] = useState([0, 0]);

  const [optimizeEnabled, setOptimizeEnabled] = useState(false);
  const [minSegmentLength, setMinSegmentLength] = useState(0.5);
  const [collinearAngleEpsDeg, setCollinearAngleEpsDeg] = useState(1.0);
  const [rdpEpsilon, setRdpEpsilon] = useState(0);
  const [generatedScriptRaw, setGeneratedScriptRaw] = useState("");
  const [generatedScriptOptimized, setGeneratedScriptOptimized] = useState("");
  const [scriptViewTab, setScriptViewTab] = useState("raw");

  const [motionEnabled, setMotionEnabled] = useState(false);
  const [driftDegPerSec, setDriftDegPerSec] = useState(1.0);
  const [positionNoiseStd, setPositionNoiseStd] = useState(2.0);
  const [motionSeed, setMotionSeed] = useState("");

  const [debugViewMode, setDebugViewMode] = useState("simple");

  const [showExportModal, setShowExportModal] = useState(false);
  const [exportFormat, setExportFormat] = useState("robot_v1");
  const [exportContent, setExportContent] = useState("");
  const [exportFilename, setExportFilename] = useState("robot_export.robot_v1.txt");
  const [exportBlocked, setExportBlocked] = useState(false);
  const [exportBusy, setExportBusy] = useState(false);
  const [exportError, setExportError] = useState("");

  const optimizePayload = useMemo(() => optimizeEnabled ? {
    enabled: true,
    min_segment_length: minSegmentLength,
    collinear_angle_eps_deg: collinearAngleEpsDeg,
    rdp_epsilon: rdpEpsilon
  } : null, [optimizeEnabled, minSegmentLength, collinearAngleEpsDeg, rdpEpsilon]);

  const motionPayload = useMemo(() => {
    if (!motionEnabled) return { enabled: false };
    const seedNum = motionSeed.trim() === "" ? null : parseInt(motionSeed, 10);
    return {
      enabled: true,
      drift_deg_per_sec: driftDegPerSec,
      position_noise_std_per_sec: positionNoiseStd,
      ...(Number.isInteger(seedNum) ? { seed: seedNum } : {})
    };
  }, [motionEnabled, driftDegPerSec, positionNoiseStd, motionSeed]);

  const effectiveBounds = useMemo(() => {
    if (result?.stats?.bounds && result.stats.bounds.length === 4) return result.stats.bounds;
    const pts = [];
    walls.forEach(w => {
      if (w.length >= 4) { pts.push(w[0], w[1]); pts.push(w[2], w[3]); }
    });
    rawPath.forEach(p => { if (p.length >= 2) pts.push(p[0], p[1]); });
    if (pts.length < 2) return null;
    let minx = pts[0], maxx = pts[0], miny = pts[1], maxy = pts[1];
    for (let i = 0; i < pts.length; i += 2) {
      const x = pts[i], y = pts[i + 1];
      if (x < minx) minx = x; if (x > maxx) maxx = x;
      if (y < miny) miny = y; if (y > maxy) maxy = y;
    }
    return [minx, miny, maxx, maxy];
  }, [result?.stats?.bounds, walls, rawPath]);

  useEffect(() => {
    boundsRef.current = effectiveBounds;
  }, [effectiveBounds]);

  useEffect(() => {
    try {
      localStorage.setItem(PLAN_STORAGE_KEY, JSON.stringify(planList));
    } catch (_) {}
  }, [planList]);

  useEffect(() => {
    tickStateRef.current = tickState;
  }, [tickState]);

  const blocked = result?.blocked ?? false;
  const parserErr = useMemo(() => (result?.parser || []).filter(d => d.severity === "ERROR").length, [result]);
  const parserWarn = useMemo(() => (result?.parser || []).filter(d => d.severity === "WARN").length, [result]);
  const analysisErr = useMemo(() => (result?.analysis || []).filter(d => d.severity === "ERROR").length, [result]);
  const analysisWarn = useMemo(() => (result?.analysis || []).filter(d => d.severity === "WARN").length, [result]);

  const worldToScreen = useCallback((x, y) => {
    const v = viewRef.current;
    return {
      sx: x * v.scale + v.offsetX,
      sy: -y * v.scale + v.offsetY
    };
  }, []);

  const screenToWorld = useCallback((sx, sy) => {
    const v = viewRef.current;
    return {
      x: (sx - v.offsetX) / v.scale,
      y: -(sy - v.offsetY) / v.scale
    };
  }, []);

  const redrawCanvas = useCallback((lastTick) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const w = canvas.width;
    const h = canvas.height;
    ctx.fillStyle = "#0b0b0b";
    ctx.fillRect(0, 0, w, h);
    if (showWalls && walls.length > 0) {
      ctx.strokeStyle = "#666";
      ctx.lineWidth = 1;
      ctx.beginPath();
      walls.forEach(seg => {
        if (seg.length >= 4) {
          const a = worldToScreen(seg[0], seg[1]);
          const b = worldToScreen(seg[2], seg[3]);
          ctx.moveTo(a.sx, a.sy);
          ctx.lineTo(b.sx, b.sy);
        }
      });
      ctx.stroke();
    }
    if (showPathPreview && rawPath.length > 1) {
      ctx.strokeStyle = "#3b82f6";
      ctx.lineWidth = 1;
      ctx.beginPath();
      const first = worldToScreen(rawPath[0][0], rawPath[0][1]);
      ctx.moveTo(first.sx, first.sy);
      for (let i = 1; i < rawPath.length; i++) {
        const p = worldToScreen(rawPath[i][0], rawPath[i][1]);
        ctx.lineTo(p.sx, p.sy);
      }
      ctx.stroke();
    }
    const ghostPoints = result?.stats?.path_points;
    if (showGhostPath && ghostPoints && ghostPoints.length > 1) {
      ctx.strokeStyle = "rgba(148, 163, 184, 0.5)";
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      const first = worldToScreen(ghostPoints[0][0], ghostPoints[0][1]);
      ctx.moveTo(first.sx, first.sy);
      for (let i = 1; i < ghostPoints.length; i++) {
        const p = worldToScreen(ghostPoints[i][0], ghostPoints[i][1]);
        ctx.lineTo(p.sx, p.sy);
      }
      ctx.stroke();
      ctx.setLineDash([]);
    }
    const trace = traceRef.current;
    let prev = null;
    for (let i = 0; i < trace.length; i++) {
      const p = trace[i];
      const err = p.error ?? 0;
      const width = 1 + Math.min(6, err / 10);
      const alpha = Math.min(1, Math.max(0.2, 0.2 + err / 200));
      const { sx, sy } = worldToScreen(p.x, p.y);
      if (p.pen && prev) {
        ctx.strokeStyle = `rgba(74, 222, 128, ${alpha})`;
        ctx.lineWidth = width;
        ctx.beginPath();
        ctx.moveTo(prev.sx, prev.sy);
        ctx.lineTo(sx, sy);
        ctx.stroke();
      }
      prev = p.pen ? { sx, sy } : null;
    }
    if (lastTick) {
      const rx = lastTick.real_x ?? lastTick.x;
      const ry = lastTick.real_y ?? lastTick.y;
      const { sx, sy } = worldToScreen(rx, ry);
      ctx.fillStyle = lastTick.pen ? "#22c55e" : "#64748b";
      ctx.beginPath();
      ctx.arc(sx, sy, 4, 0, Math.PI * 2);
      ctx.fill();
    }
    if (startPoint && startPoint.length >= 2) {
      const { sx, sy } = worldToScreen(startPoint[0], startPoint[1]);
      ctx.strokeStyle = "#22c55e";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(sx, sy, 6, 0, Math.PI * 2);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(sx - 5, sy);
      ctx.lineTo(sx + 5, sy);
      ctx.moveTo(sx, sy - 5);
      ctx.lineTo(sx, sy + 5);
      ctx.stroke();
    }

    if (showCollisions && collisionsSample.length > 0) {
      ctx.save();
      ctx.strokeStyle = "#ef4444";
      ctx.fillStyle = "#ef4444";
      collisionsSample.forEach((c) => {
        if (c.x == null || c.y == null) return;
        const { sx, sy } = worldToScreen(c.x, c.y);
        ctx.beginPath();
        ctx.arc(sx, sy, 4, 0, Math.PI * 2);
        ctx.fill();
      });
      ctx.restore();
    }
  }, [worldToScreen, showWalls, showPathPreview, showGhostPath, showCollisions, walls, rawPath, startPoint, result?.stats?.path_points, collisionsSample]);

  const flushOneAndDraw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let lastPayload = null;
    while (queueRef.current.length > 0) {
      const payload = queueRef.current.shift();
      traceRef.current.push({
        x: payload.real_x ?? payload.x,
        y: payload.real_y ?? payload.y,
        idealX: payload.ideal_x,
        idealY: payload.ideal_y,
        error: payload.error ?? 0,
        pen: payload.pen,
        drew: payload.drew
      });
      setTickState(payload);
      lastPayload = payload;
    }
    redrawCanvas(lastPayload || tickStateRef.current);
  }, [redrawCanvas]);

  const rafLoop = useCallback(() => {
    if (queueRef.current.length > 0) flushOneAndDraw();
    rafIdRef.current = requestAnimationFrame(rafLoop);
  }, [flushOneAndDraw]);

  useEffect(() => {
    if (activeTab === "w2" && canvasRef.current) {
      const w = canvasRef.current.width;
      const h = canvasRef.current.height;
      viewRef.current = computeFitView(boundsRef.current, w, h, MARGIN);
      redrawCanvas(tickStateRef.current);
    }
  }, [activeTab, redrawCanvas]);

  const handleClearCanvas = useCallback(() => {
    if (rafIdRef.current != null) {
      cancelAnimationFrame(rafIdRef.current);
      rafIdRef.current = null;
    }
    queueRef.current = [];
    traceRef.current = [];
    setTickState(null);
    setBlockedSim(null);
    setSimulateError("");
    if (canvasRef.current) {
      viewRef.current = computeFitView(boundsRef.current, canvasRef.current.width, canvasRef.current.height, MARGIN);
    }
    redrawCanvas(null);
  }, [redrawCanvas]);

  const handleFitView = useCallback(() => {
    if (canvasRef.current) {
      viewRef.current = computeFitView(boundsRef.current, canvasRef.current.width, canvasRef.current.height, MARGIN);
      redrawCanvas(tickStateRef.current);
    }
  }, [redrawCanvas]);

  const handleResetView = useCallback(() => {
    if (canvasRef.current) {
      const w = canvasRef.current.width;
      const h = canvasRef.current.height;
      viewRef.current = resetView(w, h);
      redrawCanvas(tickStateRef.current);
    }
  }, [redrawCanvas]);

  async function onStartSimulate() {
    setSimulateError("");
    setBlockedSim(null);
    if (rafIdRef.current != null) cancelAnimationFrame(rafIdRef.current);
    queueRef.current = [];
    rafIdRef.current = requestAnimationFrame(rafLoop);
    const ac = new AbortController();
    simAbortRef.current = ac;
    setSimRunning(true);
    traceRef.current = [];
    setTickState(null);
    if (canvasRef.current) {
      viewRef.current = computeFitView(boundsRef.current, canvasRef.current.width, canvasRef.current.height, MARGIN);
    }
    const onEvent = (eventName, payload) => {
      if (eventName === "tick") queueRef.current.push(payload);
      else if (eventName === "done") {
        setTickState(prev => (prev ? { ...prev, ...payload, finished: true } : { ...payload, finished: true }));
        setSimRunning(false);
        if (rafIdRef.current != null) {
          cancelAnimationFrame(rafIdRef.current);
          rafIdRef.current = null;
        }
      } else if (eventName === "error") {
        setSimulateError(payload.message || "Simülasyon hatası");
        setSimRunning(false);
        if (rafIdRef.current != null) {
          cancelAnimationFrame(rafIdRef.current);
          rafIdRef.current = null;
        }
      }
    };
    try {
      const out = await createJob(script, { dt: 0.016, speed_multiplier: speedMultiplier, start: startPoint, optimize: optimizePayload, motion: motionPayload, walls, collisionMode: "warn" });
      if (!out.ok) {
        setBlockedSim(out);
        setSimRunning(false);
        if (rafIdRef.current != null) {
          cancelAnimationFrame(rafIdRef.current);
          rafIdRef.current = null;
        }
        return;
      }
      jobIdRef.current = out.job_id;
      await getJobStream(out.job_id, onEvent, ac.signal);
      jobIdRef.current = null;
      setSimRunning(false);
      if (rafIdRef.current != null) {
        cancelAnimationFrame(rafIdRef.current);
        rafIdRef.current = null;
      }
    } catch (e) {
      jobIdRef.current = null;
      if (e?.name === "AbortError") {
        setSimRunning(false);
        if (rafIdRef.current != null) {
          cancelAnimationFrame(rafIdRef.current);
          rafIdRef.current = null;
        }
        return;
      }
      setSimulateError(String(e?.message || e));
      setSimRunning(false);
      if (rafIdRef.current != null) {
        cancelAnimationFrame(rafIdRef.current);
        rafIdRef.current = null;
      }
    }
  }

  async function onStopSimulate() {
    if (jobIdRef.current) {
      await stopJob(jobIdRef.current);
      jobIdRef.current = null;
    }
    if (simAbortRef.current) {
      simAbortRef.current.abort();
      simAbortRef.current = null;
    }
    if (rafIdRef.current != null) {
      cancelAnimationFrame(rafIdRef.current);
      rafIdRef.current = null;
    }
    queueRef.current = [];
  }

  async function onAnalyze() {
    setErr("");
    setBusy(true);
    try {
      const res = await analyzeScenario(script, startPoint, optimizePayload, walls, "warn");
      setResult(res);
      const s = res?.stats;
      setCollisionCount(s?.collision_count ?? 0);
      setCollisionsSample((s?.collisions_sample ?? []).slice(0, 50));
    } catch (e) {
      setErr(String(e?.message || e));
    } finally {
      setBusy(false);
    }
  }

  function onSavePlan() {
    const name = (planName || "Unnamed").trim();
    const options = { step_size: stepSize, speed: planSpeed, world_scale: worldScale, world_offset: [worldOffsetX, worldOffsetY] };
    if (selectedPlanId) {
      setPlanList(prev => prev.map(p => p.id === selectedPlanId ? { ...p, name, plan_text: planText, options, updated_at: new Date().toISOString() } : p));
    } else {
      const id = `plan-${Date.now()}`;
      setPlanList(prev => [...prev, { id, name, plan_text: planText, options, updated_at: new Date().toISOString() }]);
      setSelectedPlanId(id);
    }
  }

  function onLoadPlan(id) {
    setSelectedPlanId(id);
    const p = planList.find(x => x.id === id);
    if (!p) return;
    setPlanName(p.name ?? "");
    setPlanText(p.plan_text ?? "");
    setStepSize(p.options?.step_size ?? 5);
    setPlanSpeed(p.options?.speed ?? 120);
    setWorldScale(p.options?.world_scale ?? 1);
    setWorldOffsetX(Array.isArray(p.options?.world_offset) ? p.options.world_offset[0] : 0);
    setWorldOffsetY(Array.isArray(p.options?.world_offset) ? p.options.world_offset[1] : 0);
  }

  function onDeletePlan() {
    if (!selectedPlanId) return;
    setPlanList(prev => prev.filter(p => p.id !== selectedPlanId));
    setSelectedPlanId("");
  }

  async function onGenerateScript() {
    setCompileError("");
    setCompileBusy(true);
    setGeneratedScript("");
    setGeneratedScriptRaw("");
    setGeneratedScriptOptimized("");
    try {
      const res = await compilePlan(planText, {
        step_size: stepSize,
        speed: planSpeed,
        world_scale: worldScale,
        world_offset: [worldOffsetX, worldOffsetY],
        optimize: optimizePayload
      });
      if (!res.ok) {
        setCompileError(res.error || "Plan derlenemedi");
        return;
      }
      const raw = res.commands_text_raw ?? res.commands_text ?? "";
      const opt = res.commands_text_optimized ?? raw;
      setGeneratedScriptRaw(raw);
      setGeneratedScriptOptimized(opt);
      setGeneratedScript(raw);
      setScript(raw);
      setWalls(res.walls ?? []);
      setRawPath(res.raw_path_points ?? []);
      const analyzeRes = await analyzeScenario(opt, startPoint, optimizePayload, res.walls ?? [], "warn");
      setResult(analyzeRes);
      const s = analyzeRes?.stats;
      setCollisionCount(s?.collision_count ?? 0);
      setCollisionsSample((s?.collisions_sample ?? []).slice(0, 50));
    } catch (e) {
      const msg = String(e?.message || e);
      setCompileError(msg === "Failed to fetch" ? "Backend'e ulaşılamadı. Backend çalışıyor mu? (http://127.0.0.1:8000)" : msg);
    } finally {
      setCompileBusy(false);
    }
  }

  function onSelectScriptTab(tab) {
    setScriptViewTab(tab);
    if (tab === "raw") setScript(generatedScriptRaw || script);
    else setScript(generatedScriptOptimized || script);
  }

  function handleLoadExample() {
    setScript(DEFAULT_SCRIPT);
    setResult(null);
    setErr("");
  }

  function handleClearScript() {
    setScript("");
    setResult(null);
    setErr("");
  }

  const editorArea = (
    <div style={{ border: "1px solid #333", borderRadius: 12, padding: 12, boxShadow: "0 10px 24px rgba(0,0,0,0.4)" }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8, marginBottom: 8 }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 2 }}>Komut editörü</div>
          <div style={{ fontSize: 12, opacity: 0.75 }}>SPEED, PEN, MOVE, TURN, FORWARD, REPEAT… desteklenir</div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            type="button"
            onClick={handleLoadExample}
            style={{
              padding: "6px 10px",
              borderRadius: 8,
              border: "1px solid #444",
              background: "#1d3b7a",
              color: "#fff",
              fontSize: 12,
              cursor: "pointer",
              fontWeight: 600
            }}
          >
            Örnek yükle
          </button>
          <button
            type="button"
            onClick={handleClearScript}
            style={{
              padding: "6px 10px",
              borderRadius: 8,
              border: "1px solid #444",
              background: "#333",
              color: "#eee",
              fontSize: 12,
              cursor: "pointer",
              fontWeight: 600
            }}
          >
            Temizle
          </button>
        </div>
      </div>
      <textarea
        value={script}
        onChange={(e) => setScript(e.target.value)}
        spellCheck={false}
        style={{
          width: "100%",
          height: activeTab === "w2" ? 320 : 520,
          marginTop: 4,
          borderRadius: 10,
          border: "1px solid #333",
          background: "#0b0b0b",
          color: "#eee",
          padding: 12,
          fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
          fontSize: 13,
          lineHeight: 1.35
        }}
      />
    </div>
  );

  return (
    <div style={{ minHeight: "100vh", background: "#111", color: "#eee", padding: 18, fontFamily: "system-ui" }}>
      <h2 style={{ margin: 0 }}>PlanDraw — Scenario</h2>
      <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
        <button
          onClick={() => setActiveTab("w1")}
          style={{
            padding: "8px 14px",
            borderRadius: 8,
            border: "1px solid #444",
            background: activeTab === "w1" ? "#1d3b7a" : "#222",
            color: "#fff",
            cursor: "pointer",
            fontWeight: 600
          }}
        >
          W1 Analyze
        </button>
        <button
          onClick={() => setActiveTab("w2")}
          style={{
            padding: "8px 14px",
            borderRadius: 8,
            border: "1px solid #444",
            background: activeTab === "w2" ? "#1d3b7a" : "#222",
            color: "#fff",
            cursor: "pointer",
            fontWeight: 600
          }}
        >
          W2 Çizim
        </button>
        <button
          onClick={() => setActiveTab("w3")}
          style={{
            padding: "8px 14px",
            borderRadius: 8,
            border: "1px solid #444",
            background: activeTab === "w3" ? "#1d3b7a" : "#222",
            color: "#fff",
            cursor: "pointer",
            fontWeight: 600
          }}
        >
          W3 Plan
        </button>
      </div>

      {activeTab === "w1" && (
        <div style={{ display: "grid", gridTemplateColumns: "1.3fr 0.9fr", gap: 18, marginTop: 16 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10, flexWrap: "wrap" }}>
              <button
                onClick={onAnalyze}
                disabled={busy}
                style={{
                  padding: "10px 16px",
                  borderRadius: 10,
                  border: "1px solid #1d4ed8",
                  background: busy ? "#222" : "#1d3b7a",
                  color: "#fff",
                  cursor: busy ? "not-allowed" : "pointer",
                  fontWeight: 700,
                  fontSize: 14,
                  boxShadow: busy ? "none" : "0 10px 24px rgba(15,23,42,0.7)"
                }}
              >
                {busy ? "Analyzing..." : "Analyze"}
              </button>
              {result ? <Badge ok={!blocked} text={blocked ? "BLOCKED" : "SAFE"} /> : null}
              {result?.stats && (
                <div style={{ fontSize: 12, opacity: 0.8 }}>
                  ⏱ Yaklaşık süre: {formatSecondsShort(result.stats.estimated_time)} · 📐 Alan:{" "}
                  {formatBoundsHuman(result.stats.bounds)}
                </div>
              )}
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 12, marginBottom: 10 }}>
              <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, cursor: "pointer" }}>
                <input type="checkbox" checked={optimizeEnabled} onChange={(e) => setOptimizeEnabled(e.target.checked)} />
                Optimize (W4)
              </label>
              {optimizeEnabled && (
                <>
                  <label style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12 }}>
                    min_seg
                    <input type="number" min={0} step={0.1} value={minSegmentLength} onChange={(e) => setMinSegmentLength(Number(e.target.value))} style={{ width: 52, padding: 4, background: "#222", color: "#eee", border: "1px solid #444" }} />
                  </label>
                  <label style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12 }}>
                    angle_°
                    <input type="number" min={0} max={10} step={0.5} value={collinearAngleEpsDeg} onChange={(e) => setCollinearAngleEpsDeg(Number(e.target.value))} style={{ width: 52, padding: 4, background: "#222", color: "#eee", border: "1px solid #444" }} />
                  </label>
                  <label style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12 }}>
                    RDP ε
                    <input type="number" min={0} step={0.1} value={rdpEpsilon} onChange={(e) => setRdpEpsilon(Number(e.target.value))} style={{ width: 52, padding: 4, background: "#222", color: "#eee", border: "1px solid #444" }} />
                  </label>
                </>
              )}
            </div>
            {err ? <div style={{ marginTop: 10, color: "#ff7070" }}>{err}</div> : null}
            {editorArea}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div
              style={{
                border: "1px solid #333",
                borderRadius: 12,
                padding: 14,
                background: "#151515",
                boxShadow: "0 10px 25px rgba(0,0,0,0.45)"
              }}
            >
              <div style={{ fontWeight: 800, marginBottom: 10, fontSize: 15 }}>Durum</div>
              {result ? (
                <>
                  <StatusBadgeLarge blocked={blocked} />
                  {collisionCount > 0 && (
                    <div style={{ marginTop: 8, fontSize: 12, color: "#facc15" }}>
                      ⚠ Duvarlarla kesişim: <b>{collisionCount}</b>
                    </div>
                  )}
                </>
              ) : (
                <div style={{ fontSize: 13, opacity: 0.7 }}>Önce senaryoyu analiz edin.</div>
              )}
            </div>

            <div
              style={{
                border: "1px solid #333",
                borderRadius: 12,
                padding: 14,
                background: "#151515",
                boxShadow: "0 10px 25px rgba(0,0,0,0.45)"
              }}
            >
              <div style={{ fontWeight: 800, marginBottom: 8, fontSize: 15 }}>Hızlı özet</div>
              {result?.stats ? (
                <div style={{ fontSize: 13, lineHeight: 1.6 }}>
                  <div>
                    🧭 Çizim alanı: <b>{formatBoundsHuman(result.stats.bounds)}</b>
                  </div>
                  <div>
                    ⏱ Yaklaşık süre: <b>{formatSecondsShort(result.stats.estimated_time)}</b>
                  </div>
                  <div>
                    📏 Toplam çizgi uzunluğu: <b>{formatNumberCompact(result.stats.path_length, 1)} unit</b>
                  </div>
                  <div>
                    🔁 Hareket sayısı: <b>{result.stats.move_count ?? "—"}</b>
                  </div>
                  <div>
                    🧱 Çakışma sayısı: <b>{collisionCount}</b>
                  </div>
                  {result.stats.original_move_count != null && result.stats.optimized_move_count != null && (
                    <div style={{ marginTop: 4 }}>
                      ✨ Optimizasyon:{" "}
                      <b>
                        {result.stats.reduction_ratio != null
                          ? `${Number(result.stats.reduction_ratio).toFixed(1)}% azaldı`
                          : "aktif"}
                      </b>{" "}
                      ({result.stats.original_move_count} → {result.stats.optimized_move_count})
                    </div>
                  )}
                </div>
              ) : (
                <div style={{ fontSize: 13, opacity: 0.7 }}>Henüz özet yok. "Analyze" ile başlatın.</div>
              )}
            </div>

            <Accordion
              title="Sorunlar"
              subtitle={`Parser: ${parserErr} err / ${parserWarn} warn · Analysis: ${analysisErr} err / ${analysisWarn} warn`}
              defaultOpen={false}
            >
              {(!result || ((result.parser || []).length === 0 && (result.analysis || []).length === 0)) ? (
                <div style={{ opacity: 0.85 }}>Her şey temiz ✅</div>
              ) : (
                <>
                  <div style={{ marginBottom: 8 }}>
                    <div style={{ fontWeight: 700, fontSize: 12, color: "#fca5a5", marginBottom: 4 }}>Parser</div>
                    {(result.parser || []).filter((d) => d.severity === "ERROR").map((d, idx) => (
                      <div key={`perr-${idx}`} style={{ marginBottom: 6, padding: 6, borderRadius: 6, background: "#3b0a0a" }}>
                        <div style={{ fontWeight: 600, fontSize: 12 }}>❌ Satır {d.line}</div>
                        <div style={{ fontSize: 12 }}>{d.message}</div>
                        {d.text ? (
                          <div style={{ marginTop: 4, fontFamily: "monospace", fontSize: 11, opacity: 0.85 }}>{d.text}</div>
                        ) : null}
                      </div>
                    ))}
                    {(result.parser || []).filter((d) => d.severity === "WARN").map((d, idx) => (
                      <div key={`pwarn-${idx}`} style={{ marginBottom: 6, padding: 6, borderRadius: 6, background: "#3f2e00" }}>
                        <div style={{ fontWeight: 600, fontSize: 12 }}>⚠ Satır {d.line}</div>
                        <div style={{ fontSize: 12 }}>{d.message}</div>
                        {d.text ? (
                          <div style={{ marginTop: 4, fontFamily: "monospace", fontSize: 11, opacity: 0.85 }}>{d.text}</div>
                        ) : null}
                      </div>
                    ))}
                    {(result.parser || []).length === 0 && <div style={{ opacity: 0.8 }}>Parser tarafında sorun yok.</div>}
                  </div>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: 12, color: "#fca5a5", marginBottom: 4 }}>Analysis</div>
                    {(result.analysis || []).filter((d) => d.severity === "ERROR").map((d, idx) => (
                      <div key={`aerr-${idx}`} style={{ marginBottom: 6, padding: 6, borderRadius: 6, background: "#3b0a0a" }}>
                        <div style={{ fontWeight: 600, fontSize: 12 }}>❌ Satır {d.line}</div>
                        <div style={{ fontSize: 12 }}>{d.message}</div>
                        {d.text ? (
                          <div style={{ marginTop: 4, fontFamily: "monospace", fontSize: 11, opacity: 0.85 }}>{d.text}</div>
                        ) : null}
                      </div>
                    ))}
                    {(result.analysis || []).filter((d) => d.severity === "WARN").map((d, idx) => (
                      <div key={`awarn-${idx}`} style={{ marginBottom: 6, padding: 6, borderRadius: 6, background: "#3f2e00" }}>
                        <div style={{ fontWeight: 600, fontSize: 12 }}>⚠ Satır {d.line}</div>
                        <div style={{ fontSize: 12 }}>{d.message}</div>
                        {d.text ? (
                          <div style={{ marginTop: 4, fontFamily: "monospace", fontSize: 11, opacity: 0.85 }}>{d.text}</div>
                        ) : null}
                      </div>
                    ))}
                    {(result.analysis || []).length === 0 && <div style={{ opacity: 0.8 }}>Analysis tarafında sorun yok.</div>}
                  </div>
                </>
              )}
            </Accordion>

            <Accordion title="Geliştirici detayı" subtitle="Unrolled komutlar ve ham istatistikler" defaultOpen={false}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                <div style={{ fontWeight: 600, fontSize: 12 }}>Ham veriler</div>
                <button
                  type="button"
                  onClick={() => {
                    const parts = [];
                    if (result?.commands_unrolled) parts.push(result.commands_unrolled);
                    if (result?.stats) parts.push(JSON.stringify(result.stats, null, 2));
                    const text = parts.join("\n\n--- stats ---\n\n");
                    if (text && navigator.clipboard?.writeText) {
                      navigator.clipboard.writeText(text);
                    }
                  }}
                  style={{
                    padding: "4px 8px",
                    borderRadius: 6,
                    border: "1px solid #444",
                    background: "#222",
                    color: "#eee",
                    fontSize: 11,
                    cursor: "pointer"
                  }}
                >
                  Kopyala
                </button>
              </div>
              <div style={{ fontSize: 11, opacity: 0.8, marginBottom: 6 }}>İçerik yalnızca görüntü amaçlıdır; backend çıktısı değiştirilmez.</div>
              <div style={{ marginBottom: 8 }}>
                <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 4 }}>Stats (JSON)</div>
                <pre
                  style={{
                    maxHeight: 140,
                    overflow: "auto",
                    border: "1px solid #333",
                    borderRadius: 8,
                    padding: 8,
                    background: "#0b0b0b",
                    fontSize: 11
                  }}
                >
                  {result?.stats ? JSON.stringify(result.stats, null, 2) : "{}"}
                </pre>
              </div>
              <div>
                <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 4 }}>Unrolled commands</div>
                <textarea
                  readOnly
                  value={result?.commands_unrolled || ""}
                  style={{
                    width: "100%",
                    maxHeight: 160,
                    borderRadius: 8,
                    border: "1px solid #333",
                    background: "#0b0b0b",
                    color: "#eee",
                    padding: 8,
                    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                    fontSize: 11,
                    lineHeight: 1.35,
                    resize: "vertical"
                  }}
                />
              </div>
            </Accordion>
          </div>
        </div>
      )}

      {activeTab === "w2" && (
        <>
          {blockedSim && (
            <div style={{ marginTop: 12, padding: 12, background: "#3d1010", border: "1px solid #a33", borderRadius: 10 }}>
              <div style={{ fontWeight: 800, marginBottom: 8 }}>BLOCKED — Simülasyon başlatılamadı</div>
              <DiagList title="Parser" items={blockedSim.parser_diags || []} />
              <DiagList title="Analysis" items={blockedSim.analysis_diags || []} />
            </div>
          )}
          {simulateError && (
            <div style={{ marginTop: 12, color: "#ff7070" }}>{simulateError}</div>
          )}
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 12, flexWrap: "wrap" }}>
            {result ? <Badge ok={!blocked} text={blocked ? "BLOCKED" : "SAFE"} /> : null}
            <span style={{ fontSize: 12, opacity: 0.8 }}>Parser: {parserErr} err, {parserWarn} warn · Analysis: {analysisErr} err, {analysisWarn} warn</span>
            {collisionCount > 0 && (
              <span style={{ fontSize: 12, color: "#facc15" }}>⚠ Collisions: {collisionCount}</span>
            )}
            <button
              onClick={onAnalyze}
              disabled={busy}
              style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #444", background: busy ? "#222" : "#1d3b7a", color: "#fff", cursor: busy ? "not-allowed" : "pointer", fontWeight: 600 }}
            >
              {busy ? "Analyzing..." : "Analyze"}
            </button>
            <button
              onClick={onStartSimulate}
              disabled={simRunning || busy}
              style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #444", background: simRunning || busy ? "#222" : "#166534", color: "#fff", cursor: simRunning || busy ? "not-allowed" : "pointer", fontWeight: 600 }}
            >
              {simRunning ? "Çiziliyor…" : "Çiz (W2)"}
            </button>
            <button
              onClick={onStopSimulate}
              disabled={!simRunning}
              style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #444", background: !simRunning ? "#222" : "#991b1b", color: "#fff", cursor: !simRunning ? "not-allowed" : "pointer", fontWeight: 600 }}
            >
              Stop
            </button>
            <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 13 }}>Hız:</span>
              <input
                type="range"
                min={0.2}
                max={3}
                step={0.1}
                value={speedMultiplier}
                onChange={(e) => setSpeedMultiplier(Number(e.target.value))}
                disabled={simRunning}
                style={{ width: 100 }}
              />
              <span style={{ fontSize: 13, minWidth: 36 }}>{speedMultiplier.toFixed(1)}x</span>
            </label>
            <button
              onClick={handleClearCanvas}
              style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #444", background: "#333", color: "#fff", cursor: "pointer", fontWeight: 600 }}
            >
              CLEAR
            </button>
            <button
              onClick={handleFitView}
              style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #444", background: "#333", color: "#fff", cursor: "pointer", fontWeight: 600 }}
            >
              Fit
            </button>
            <button
              onClick={handleResetView}
              style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #444", background: "#333", color: "#fff", cursor: "pointer", fontWeight: 600 }}
            >
              Reset view
            </button>
            <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, cursor: "pointer" }}>
              <input type="checkbox" checked={motionEnabled} onChange={(e) => setMotionEnabled(e.target.checked)} disabled={simRunning} />
              Motion error (W5)
            </label>
            {motionEnabled && (
              <>
                <label style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12 }}>
                  Drift °/s
                  <input type="number" min={0} step={0.5} value={driftDegPerSec} onChange={(e) => setDriftDegPerSec(Number(e.target.value))} disabled={simRunning} style={{ width: 56, padding: 4, background: "#222", color: "#eee", border: "1px solid #444" }} />
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12 }}>
                  Noise √s
                  <input type="number" min={0} step={0.5} value={positionNoiseStd} onChange={(e) => setPositionNoiseStd(Number(e.target.value))} disabled={simRunning} style={{ width: 56, padding: 4, background: "#222", color: "#eee", border: "1px solid #444" }} />
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12 }}>
                  Seed
                  <input type="text" placeholder="opsiyonel" value={motionSeed} onChange={(e) => setMotionSeed(e.target.value)} disabled={simRunning} style={{ width: 64, padding: 4, background: "#222", color: "#eee", border: "1px solid #444" }} />
                </label>
              </>
            )}
            <button
              onClick={() => { setShowExportModal(true); setExportContent(""); setExportError(""); setExportBlocked(false); }}
              style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #444", background: "#333", color: "#fff", cursor: "pointer", fontWeight: 600 }}
            >
              Export (W6)
            </button>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginTop: 14 }}>
            <div>{editorArea}</div>
            <div
              style={{ border: "1px solid #333", borderRadius: 12, padding: 12 }}
              onWheel={(e) => e.preventDefault()}
              role="presentation"
            >
              <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 8 }}>
                <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, cursor: "pointer" }}>
                  <input type="checkbox" checked={showWalls} onChange={(e) => setShowWalls(e.target.checked)} />
                  Show walls
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, cursor: "pointer" }}>
                  <input type="checkbox" checked={showPathPreview} onChange={(e) => setShowPathPreview(e.target.checked)} />
                  Show path preview
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, cursor: "pointer" }}>
                  <input type="checkbox" checked={showGhostPath} onChange={(e) => setShowGhostPath(e.target.checked)} />
                  Show ghost path
                </label>
              </div>
              <canvas
                ref={canvasRef}
                width={600}
                height={400}
                style={{ width: "100%", maxWidth: 600, height: 400, background: "#0b0b0b", borderRadius: 8, display: "block", cursor: "crosshair" }}
                onClick={(e) => {
                  if (skippedClickRef.current) {
                    skippedClickRef.current = false;
                    return;
                  }
                  const canvas = canvasRef.current;
                  if (!canvas || simRunning) return;
                  const rect = canvas.getBoundingClientRect();
                  const sx = (e.clientX - rect.left) * (canvas.width / rect.width);
                  const sy = (e.clientY - rect.top) * (canvas.height / rect.height);
                  const { x, y } = screenToWorld(sx, sy);
                  setStartPoint([x, y]);
                  redrawCanvas(tickStateRef.current);
                }}
                onMouseDown={(e) => {
                  const canvas = canvasRef.current;
                  if (!canvas) return;
                  const rect = canvas.getBoundingClientRect();
                  const sx = (e.clientX - rect.left) * (canvas.width / rect.width);
                  const sy = (e.clientY - rect.top) * (canvas.height / rect.height);
                  panStartRef.current = { sx, sy, offsetX: viewRef.current.offsetX, offsetY: viewRef.current.offsetY, moved: false };
                }}
                onMouseMove={(e) => {
                  if (!panStartRef.current) return;
                  const canvas = canvasRef.current;
                  if (!canvas) return;
                  const rect = canvas.getBoundingClientRect();
                  const sx = (e.clientX - rect.left) * (canvas.width / rect.width);
                  const sy = (e.clientY - rect.top) * (canvas.height / rect.height);
                  const dx = sx - panStartRef.current.sx;
                  const dy = sy - panStartRef.current.sy;
                  panStartRef.current.moved = true;
                  viewRef.current = {
                    ...viewRef.current,
                    offsetX: panStartRef.current.offsetX + dx,
                    offsetY: panStartRef.current.offsetY + dy
                  };
                  redrawCanvas(tickStateRef.current);
                }}
                onMouseLeave={() => { panStartRef.current = null; }}
                onMouseUp={() => {
                  if (panStartRef.current) {
                    skippedClickRef.current = panStartRef.current.moved;
                    panStartRef.current = null;
                  }
                }}
                onWheel={(e) => {
                  e.preventDefault();
                  const canvas = canvasRef.current;
                  if (!canvas) return;
                  const rect = canvas.getBoundingClientRect();
                  const sx = (e.clientX - rect.left) * (canvas.width / rect.width);
                  const sy = (e.clientY - rect.top) * (canvas.height / rect.height);
                  const zoomFactor = Math.exp(-e.deltaY * 0.001);
                  const v = viewRef.current;
                  const newScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, v.scale * zoomFactor));
                  const pivot = screenToWorld(sx, sy);
                  viewRef.current = {
                    scale: newScale,
                    offsetX: sx - pivot.x * newScale,
                    offsetY: sy + pivot.y * newScale
                  };
                  redrawCanvas(tickStateRef.current);
                }}
              />
              <div style={{ marginTop: 10, fontSize: 12, fontFamily: "monospace", lineHeight: 1.5 }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
                  <div style={{ fontWeight: 600 }}>Canlı izleme</div>
                  <div style={{ display: "flex", gap: 6 }}>
                    <button
                      type="button"
                      onClick={() => setDebugViewMode("simple")}
                      style={{
                        padding: "2px 8px",
                        borderRadius: 999,
                        border: "1px solid #444",
                        background: debugViewMode === "simple" ? "#1d3b7a" : "#111",
                        color: "#eee",
                        fontSize: 11,
                        cursor: "pointer"
                      }}
                    >
                      Basit
                    </button>
                    <button
                      type="button"
                      onClick={() => setDebugViewMode("dev")}
                      style={{
                        padding: "2px 8px",
                        borderRadius: 999,
                        border: "1px solid #444",
                        background: debugViewMode === "dev" ? "#1d3b7a" : "#111",
                        color: "#eee",
                        fontSize: 11,
                        cursor: "pointer"
                      }}
                    >
                      Geliştirici
                    </button>
                  </div>
                </div>
                {tickState ? (
                  debugViewMode === "simple" ? (
                    <>
                      <div>
                        Konum: x={Number(tickState.real_x ?? tickState.x).toFixed(2)}, y=
                        {Number(tickState.real_y ?? tickState.y).toFixed(2)}
                      </div>
                      {motionEnabled && (tickState.error != null || tickState.error_mean != null || tickState.error_max != null) && (
                        <div>
                          Hata (anlık/ortalama/maks):{" "}
                          {Number(tickState.error ?? 0).toFixed(3)} / {Number(tickState.error_mean ?? 0).toFixed(3)} /{" "}
                          {Number(tickState.error_max ?? 0).toFixed(3)}
                        </div>
                      )}
                      <div>
                        Durum:{" "}
                        {tickState.finished
                          ? "Bitti"
                          : tickState.wait > 0
                          ? "Bekliyor"
                          : simRunning
                          ? "Çiziyor"
                          : "Hazır"}
                      </div>
                      {collisionCount > 0 && (
                        <div>Collisions: {collisionCount}</div>
                      )}
                    </>
                  ) : (
                    <>
                      <div>idx: {tickState.idx}</div>
                      <div>wait: {Number(tickState.wait ?? 0).toFixed(3)}</div>
                      <div>heading_deg: {Number(tickState.heading_deg ?? 0).toFixed(2)}</div>
                      <div>target: {tickState.target != null ? String(tickState.target) : "—"}</div>
                      <div>finished: {tickState.finished ? "true" : "false"}</div>
                      {collisionsSample.slice(0, 10).map((c, idx) => (
                        <div key={`col-${idx}`} style={{ fontSize: 11 }}>
                          {c.kind} @{" "}
                          {c.x != null && c.y != null ? `${c.x.toFixed(2)}, ${c.y.toFixed(2)}` : "None"} (wall={c.wall_index ?? "?"}, seg={c.seg_index ?? "?"})
                        </div>
                      ))}
                    </>
                  )
                ) : (
                  <div style={{ opacity: 0.7 }}>Canlı debug — simülasyon başlayınca güncellenir</div>
                )}
              </div>
            </div>
          </div>
        </>
      )}

      {showExportModal && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }} onClick={() => setShowExportModal(false)}>
          <div style={{ background: "#222", border: "1px solid #444", borderRadius: 12, padding: 20, maxWidth: 560, width: "90%", maxHeight: "85vh", overflow: "auto" }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
              <h3 style={{ margin: 0 }}>Robot Export (W6)</h3>
              <button type="button" onClick={() => setShowExportModal(false)} style={{ background: "transparent", border: "none", color: "#aaa", cursor: "pointer", fontSize: 18 }}>×</button>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
              <span style={{ fontSize: 13 }}>Format:</span>
              <select value={exportFormat} onChange={(e) => setExportFormat(e.target.value)} style={{ padding: "6px 10px", background: "#111", color: "#eee", border: "1px solid #444", borderRadius: 6 }}>
                <option value="robot_v1">ROBOT_V1</option>
                <option value="gcode_lite">GCODE_LITE</option>
              </select>
              <button
                disabled={exportBusy}
                onClick={async () => {
                  setExportBusy(true);
                  setExportError("");
                  try {
                    const res = await exportRobot(script, { start: startPoint, format: exportFormat, optimize: optimizePayload });
                    setExportContent(res.content ?? "");
                    setExportFilename(res.filename ?? "robot_export.txt");
                    setExportBlocked(res.blocked ?? false);
                  } catch (e) {
                    setExportError(String(e?.message ?? e));
                    setExportContent("");
                  } finally {
                    setExportBusy(false);
                  }
                }}
                style={{ padding: "8px 14px", borderRadius: 8, border: "1px solid #444", background: exportBusy ? "#333" : "#1d3b7a", color: "#fff", cursor: exportBusy ? "not-allowed" : "pointer", fontWeight: 600 }}
              >
                {exportBusy ? "Oluşturuluyor…" : "Oluştur"}
              </button>
            </div>
            {exportError && <div style={{ color: "#ff7070", fontSize: 13, marginBottom: 8 }}>{exportError}</div>}
            {exportBlocked && exportContent && (
              <div style={{ padding: 10, background: "#3d1010", border: "1px solid #a33", borderRadius: 8, marginBottom: 10, fontSize: 13 }}>
                BLOCKED — Export dosyası üretildi ama çalıştırma önerilmez.
              </div>
            )}
            {exportContent && (
              <>
                <div style={{ fontSize: 12, marginBottom: 6, opacity: 0.9 }}>Önizleme (ilk ~40 satır):</div>
                <textarea
                  readOnly
                  value={exportContent.split("\n").slice(0, 40).join("\n")}
                  style={{ width: "100%", height: 180, resize: "none", background: "#0b0b0b", color: "#eee", border: "1px solid #444", borderRadius: 8, padding: 10, fontFamily: "monospace", fontSize: 12 }}
                />
                <div style={{ marginTop: 10 }}>
                  <button
                    onClick={() => {
                      const blob = new Blob([exportContent], { type: "text/plain" });
                      const a = document.createElement("a");
                      a.href = URL.createObjectURL(blob);
                      a.download = exportFilename;
                      a.click();
                      URL.revokeObjectURL(a.href);
                    }}
                    style={{ padding: "8px 14px", borderRadius: 8, border: "1px solid #444", background: "#166534", color: "#fff", cursor: "pointer", fontWeight: 600 }}
                  >
                    İndir
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {activeTab === "w3" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginTop: 14 }}>
          <div style={{ border: "1px solid #333", borderRadius: 12, padding: 12 }}>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 10, marginBottom: 10 }}>
              <input
                type="text"
                placeholder="Plan adı"
                value={planName}
                onChange={(e) => setPlanName(e.target.value)}
                style={{ width: 140, padding: "6px 8px", background: "#222", color: "#eee", border: "1px solid #444", borderRadius: 6 }}
              />
              <select
                value={selectedPlanId}
                onChange={(e) => onLoadPlan(e.target.value)}
                style={{ padding: "6px 10px", background: "#222", color: "#eee", border: "1px solid #444", borderRadius: 6, minWidth: 160 }}
              >
                <option value="">— Plan seç —</option>
                {planList.map(p => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
              <button onClick={onSavePlan} style={{ padding: "6px 12px", borderRadius: 6, border: "1px solid #444", background: "#1d3b7a", color: "#fff", cursor: "pointer" }}>Save</button>
              <button onClick={onDeletePlan} disabled={!selectedPlanId} style={{ padding: "6px 12px", borderRadius: 6, border: "1px solid #444", background: selectedPlanId ? "#991b1b" : "#333", color: "#fff", cursor: selectedPlanId ? "pointer" : "not-allowed" }}>Delete</button>
            </div>
            <div style={{ fontWeight: 700, marginBottom: 8 }}>Plan metni (LINE x1 y1 x2 y2)</div>
            <textarea
              value={planText}
              onChange={(e) => setPlanText(e.target.value)}
              spellCheck={false}
              style={{
                width: "100%",
                height: 200,
                borderRadius: 8,
                border: "1px solid #333",
                background: "#0b0b0b",
                color: "#eee",
                padding: 10,
                fontFamily: "monospace",
                fontSize: 13
              }}
            />
            <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginTop: 10, alignItems: "center" }}>
              <label style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <span style={{ width: 72 }}>step_size</span>
                <input type="number" min={0.1} step={0.5} value={stepSize} onChange={(e) => setStepSize(Number(e.target.value))} style={{ width: 56, padding: 4, background: "#222", color: "#eee", border: "1px solid #444" }} />
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, cursor: "pointer" }}>
                <input type="checkbox" checked={showCollisions} onChange={(e) => setShowCollisions(e.target.checked)} />
                Show collisions
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <span style={{ width: 72 }}>speed</span>
                <input type="number" min={1} value={planSpeed} onChange={(e) => setPlanSpeed(Number(e.target.value))} style={{ width: 56, padding: 4, background: "#222", color: "#eee", border: "1px solid #444" }} />
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <span style={{ width: 72 }}>world_scale</span>
                <input type="number" min={0.01} step={0.1} value={worldScale} onChange={(e) => setWorldScale(Number(e.target.value))} style={{ width: 56, padding: 4, background: "#222", color: "#eee", border: "1px solid #444" }} />
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <span style={{ width: 72 }}>offset X</span>
                <input type="number" value={worldOffsetX} onChange={(e) => setWorldOffsetX(Number(e.target.value))} style={{ width: 56, padding: 4, background: "#222", color: "#eee", border: "1px solid #444" }} />
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <span style={{ width: 72 }}>offset Y</span>
                <input type="number" value={worldOffsetY} onChange={(e) => setWorldOffsetY(Number(e.target.value))} style={{ width: 56, padding: 4, background: "#222", color: "#eee", border: "1px solid #444" }} />
              </label>
              <button
                onClick={onGenerateScript}
                disabled={compileBusy}
                style={{ padding: "8px 14px", borderRadius: 8, border: "1px solid #444", background: compileBusy ? "#222" : "#166534", color: "#fff", cursor: compileBusy ? "not-allowed" : "pointer", fontWeight: 600 }}
              >
                {compileBusy ? "Üretiliyor…" : "Generate Script"}
              </button>
            </div>
            {compileError ? <div style={{ marginTop: 10, color: "#ff7070" }}>{compileError}</div> : null}
          </div>
          <div style={{ border: "1px solid #333", borderRadius: 12, padding: 12 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
              <span style={{ fontWeight: 700 }}>Üretilen script (W1/W2 ile paylaşılır)</span>
              <button type="button" onClick={() => onSelectScriptTab("raw")} style={{ padding: "4px 10px", borderRadius: 6, border: "1px solid #444", background: scriptViewTab === "raw" ? "#1d3b7a" : "#222", color: "#fff", cursor: "pointer", fontSize: 12 }}>Raw script</button>
              <button type="button" onClick={() => onSelectScriptTab("optimized")} style={{ padding: "4px 10px", borderRadius: 6, border: "1px solid #444", background: scriptViewTab === "optimized" ? "#1d3b7a" : "#222", color: "#fff", cursor: "pointer", fontSize: 12 }}>Optimized script</button>
            </div>
            <textarea
              readOnly
              value={scriptViewTab === "raw" ? (generatedScriptRaw || generatedScript) : (generatedScriptOptimized || generatedScript)}
              style={{
                width: "100%",
                height: 320,
                borderRadius: 8,
                border: "1px solid #333",
                background: "#0b0b0b",
                color: "#eee",
                padding: 10,
                fontFamily: "monospace",
                fontSize: 12
              }}
            />
            <div style={{ marginTop: 8, fontSize: 12, opacity: 0.8 }}>
              Generate Script sonrası Raw/Optimized seçerek script editöre uygulayabilirsiniz. W2’ye geçip Çiz ile canlı çizebilirsiniz.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
