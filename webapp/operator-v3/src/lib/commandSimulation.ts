export type SimSegmentKind = "travel" | "draw";

export const SIMULATION_MIN_DURATION_MS = 8000;
export const SIMULATION_MAX_DURATION_MS = 24000;
export const SIMULATION_MIN_SEGMENT_MS = 450;

export interface SimSegment {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  kind: SimSegmentKind;
}

export interface SimPlayback {
  runId: number;
  active: boolean;
  completed: boolean;
  progress: number;
  segmentIndex: number;
  segmentT: number;
  cursor: { x: number; y: number };
  elapsedMs: number;
  durationMs: number;
}

export interface ViewportTransform {
  toX: (x: number) => number;
  toY: (y: number) => number;
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
}

export interface SimulationParseWarning {
  line: number;
  text: string;
  message: string;
}

export interface SimulationPreviewResult {
  segments: SimSegment[];
  source: "commands" | "pathPoints" | "none";
  warnings: SimulationParseWarning[];
  error: string | null;
}

const NUMBER = "[-+]?\\d*\\.?\\d+(?:[eE][-+]?\\d+)?";
const ABSOLUTE_MOVE_RE = new RegExp(`^(MOVE|MOVE_TO|DRAW|DRAW_TO)\\s+(${NUMBER})\\s+(${NUMBER})(?:\\s|$)`, "i");
const RELATIVE_MOVE_RE = new RegExp(`^MOVE_REL\\s+(${NUMBER})\\s+(${NUMBER})(?:\\s|$)`, "i");
const FORWARD_RE = new RegExp(`^FORWARD\\s+(${NUMBER})(?:\\s|$)`, "i");
const TURN_RE = new RegExp(`^TURN\\s+(${NUMBER})(?:\\s|$)`, "i");
const SET_ORIGIN_RE = new RegExp(`^SET_ORIGIN\\s+(${NUMBER})\\s+(${NUMBER})(?:\\s|$)`, "i");
const SET_HEADING_RE = new RegExp(`^SET_HEADING\\s+(${NUMBER})(?:\\s|$)`, "i");

export function createIdlePlayback(): SimPlayback {
  return {
    runId: 0,
    active: false,
    completed: false,
    progress: 0,
    segmentIndex: 0,
    segmentT: 0,
    cursor: { x: 0, y: 0 },
    elapsedMs: 0,
    durationMs: SIMULATION_MIN_DURATION_MS,
  };
}

export function calculatePlaybackDuration(segments: SimSegment[]): number {
  if (!segments.length) return 0;
  const duration = Math.max(SIMULATION_MIN_DURATION_MS, segments.length * SIMULATION_MIN_SEGMENT_MS);
  return Math.min(SIMULATION_MAX_DURATION_MS, duration);
}

export function startPlayback(runId: number, segments: SimSegment[]): SimPlayback {
  if (!segments.length) {
    return { ...createIdlePlayback(), runId, completed: true, progress: 100, durationMs: 0 };
  }
  return {
    runId,
    active: true,
    completed: false,
    progress: 0,
    segmentIndex: 0,
    segmentT: 0,
    cursor: { x: segments[0].x1, y: segments[0].y1 },
    elapsedMs: 0,
    durationMs: calculatePlaybackDuration(segments),
  };
}

export function resetSimulationPlayback(): SimPlayback {
  return createIdlePlayback();
}

export function getSimulationProgress(state: SimPlayback): number {
  return Math.round(state.progress);
}

function segmentLength(seg: SimSegment): number {
  return Math.hypot(seg.x2 - seg.x1, seg.y2 - seg.y1);
}

function appendSegment(
  segments: SimSegment[],
  from: { x: number; y: number },
  to: { x: number; y: number },
  kind: SimSegmentKind,
) {
  if (to.x === from.x && to.y === from.y) return;
  segments.push({ x1: from.x, y1: from.y, x2: to.x, y2: to.y, kind });
}

export function parseCommandsToSimulationSegments(text: string): {
  segments: SimSegment[];
  warnings: SimulationParseWarning[];
} {
  const segments: SimSegment[] = [];
  const warnings: SimulationParseWarning[] = [];
  let x = 0;
  let y = 0;
  let headingDeg = 0;
  let penDown = false;

  for (const [idx, raw] of text.split("\n").entries()) {
    const lineNumber = idx + 1;
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const upper = line.toUpperCase();

    if (upper === "PEN DOWN" || upper === "PEN_DOWN") {
      penDown = true;
      continue;
    }
    if (upper === "PEN UP" || upper === "PEN_UP") {
      penDown = false;
      continue;
    }
    if (upper === "BEGIN" || upper === "END" || upper.startsWith("SPEED ")) continue;

    const origin = line.match(SET_ORIGIN_RE);
    if (origin) {
      x = Number(origin[1]);
      y = Number(origin[2]);
      continue;
    }

    const heading = line.match(SET_HEADING_RE);
    if (heading) {
      headingDeg = Number(heading[1]);
      continue;
    }

    const turn = line.match(TURN_RE);
    if (turn) {
      const delta = Number(turn[1]);
      if (Number.isFinite(delta)) headingDeg += delta;
      continue;
    }

    const rel = line.match(RELATIVE_MOVE_RE);
    if (rel) {
      const dx = Number(rel[1]);
      const dy = Number(rel[2]);
      if (!Number.isFinite(dx) || !Number.isFinite(dy)) {
        warnings.push({ line: lineNumber, text: raw, message: "Geçersiz göreli hareket değeri atlandı." });
        continue;
      }
      const next = { x: x + dx, y: y + dy };
      appendSegment(segments, { x, y }, next, penDown ? "draw" : "travel");
      x = next.x;
      y = next.y;
      continue;
    }

    const forward = line.match(FORWARD_RE);
    if (forward) {
      const dist = Number(forward[1]);
      if (!Number.isFinite(dist)) {
        warnings.push({ line: lineNumber, text: raw, message: "Geçersiz FORWARD değeri atlandı." });
        continue;
      }
      const rad = (headingDeg * Math.PI) / 180;
      const next = { x: x + Math.cos(rad) * dist, y: y + Math.sin(rad) * dist };
      appendSegment(segments, { x, y }, next, penDown ? "draw" : "travel");
      x = next.x;
      y = next.y;
      continue;
    }

    const move = line.match(ABSOLUTE_MOVE_RE);
    if (!move) {
      warnings.push({ line: lineNumber, text: raw, message: "Simülasyon önizlemesi bu komutu atladı." });
      continue;
    }

    const cmd = move[1].toUpperCase();
    const nx = Number(move[2]);
    const ny = Number(move[3]);
    if (!Number.isFinite(nx) || !Number.isFinite(ny)) {
      warnings.push({ line: lineNumber, text: raw, message: "Geçersiz koordinat değeri atlandı." });
      continue;
    }
    const forcedDraw = cmd === "DRAW" || cmd === "DRAW_TO";
    appendSegment(segments, { x, y }, { x: nx, y: ny }, forcedDraw ? "draw" : penDown ? "draw" : "travel");
    x = nx;
    y = ny;
  }

  return { segments, warnings };
}

export function parseCommandsToSegments(text: string): SimSegment[] {
  return parseCommandsToSimulationSegments(text).segments;
}

export function pathPointsToSegments(points: number[][]): SimSegment[] {
  if (points.length < 2) return [];
  const segments: SimSegment[] = [];
  for (let i = 1; i < points.length; i++) {
    const [x1, y1] = points[i - 1];
    const [x2, y2] = points[i];
    if (![x1, y1, x2, y2].every(Number.isFinite)) continue;
    segments.push({ x1, y1, x2, y2, kind: "draw" });
  }
  return segments;
}

export function buildSimulationPreview(
  commandsText: string,
  pathPoints: number[][],
): SimulationPreviewResult {
  if (commandsText.trim()) {
    const parsed = parseCommandsToSimulationSegments(commandsText);
    if (parsed.segments.length > 0) {
      return { segments: parsed.segments, source: "commands", warnings: parsed.warnings, error: null };
    }
    if (parsed.warnings.length > 0) {
      return {
        segments: [],
        source: "none",
        warnings: parsed.warnings,
        error: "Komutlar simülasyon önizlemesine çevrilemedi.",
      };
    }
  }

  const fallback = pathPointsToSegments(pathPoints);
  if (fallback.length > 0) {
    return { segments: fallback, source: "pathPoints", warnings: [], error: null };
  }

  return {
    segments: [],
    source: "none",
    warnings: [],
    error: commandsText.trim()
      ? "Simülasyon için çizilebilir segment bulunamadı."
      : "Simülasyon için komut verisi bulunamadı. Önce planı derleyin.",
  };
}

export function buildSimulationSegments(commandsText: string, pathPoints: number[][]): SimSegment[] {
  return buildSimulationPreview(commandsText, pathPoints).segments;
}

function locateByDistance(
  segments: SimSegment[],
  distance: number,
): { segmentIndex: number; segmentT: number; cursor: { x: number; y: number } } {
  let remaining = distance;
  for (let i = 0; i < segments.length; i++) {
    const seg = segments[i];
    const len = Math.max(segmentLength(seg), 1e-9);
    if (remaining <= len || i === segments.length - 1) {
      const t = Math.max(0, Math.min(1, remaining / len));
      return {
        segmentIndex: i,
        segmentT: t,
        cursor: {
          x: seg.x1 + (seg.x2 - seg.x1) * t,
          y: seg.y1 + (seg.y2 - seg.y1) * t,
        },
      };
    }
    remaining -= len;
  }

  const last = segments[segments.length - 1];
  return { segmentIndex: segments.length, segmentT: 1, cursor: { x: last.x2, y: last.y2 } };
}

export function tickPlayback(
  state: SimPlayback,
  segments: SimSegment[],
  dtMs: number,
  playbackRate = 1,
): SimPlayback {
  if (!state.active || state.completed || !segments.length) return state;

  const durationMs = Math.max(state.durationMs || calculatePlaybackDuration(segments), 1);
  const elapsedMs = Math.min(durationMs, state.elapsedMs + dtMs * playbackRate);
  const progress = Math.min(100, (elapsedMs / durationMs) * 100);
  const totalLen = segments.reduce((sum, s) => sum + Math.max(segmentLength(s), 1e-9), 0);

  if (elapsedMs >= durationMs) {
    const last = segments[segments.length - 1];
    return {
      ...state,
      active: false,
      completed: true,
      progress: 100,
      segmentIndex: segments.length,
      segmentT: 1,
      cursor: { x: last.x2, y: last.y2 },
      elapsedMs,
      durationMs,
    };
  }

  return {
    ...state,
    progress,
    elapsedMs,
    durationMs,
    ...locateByDistance(segments, totalLen * (progress / 100)),
  };
}

export function collectBoundsFromSegments(segments: SimSegment[]): number[][] {
  const pts: number[][] = [];
  for (const s of segments) {
    pts.push([s.x1, s.y1], [s.x2, s.y2]);
  }
  return pts;
}

export function createViewportTransform(
  points: number[][],
  width: number,
  height: number,
  pad = 36,
): ViewportTransform | null {
  if (points.length < 1) return null;
  const xs = points.map((p) => p[0]);
  const ys = points.map((p) => p[1]);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const spanX = Math.max(maxX - minX, 1e-6);
  const spanY = Math.max(maxY - minY, 1e-6);
  const scale = Math.min((width - pad * 2) / spanX, (height - pad * 2) / spanY);
  return {
    minX,
    minY,
    maxX,
    maxY,
    toX: (x: number) => pad + (x - minX) * scale,
    toY: (y: number) => height - pad - (y - minY) * scale,
  };
}
