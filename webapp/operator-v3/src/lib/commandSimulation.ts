export type SimSegmentKind = "travel" | "draw";

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
}

export interface ViewportTransform {
  toX: (x: number) => number;
  toY: (y: number) => number;
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
}

export function createIdlePlayback(): SimPlayback {
  return {
    runId: 0,
    active: false,
    completed: false,
    progress: 0,
    segmentIndex: 0,
    segmentT: 0,
    cursor: { x: 0, y: 0 },
  };
}

export function startPlayback(runId: number, segments: SimSegment[]): SimPlayback {
  if (!segments.length) {
    return { ...createIdlePlayback(), runId, completed: true, progress: 100 };
  }
  return {
    runId,
    active: true,
    completed: false,
    progress: 0,
    segmentIndex: 0,
    segmentT: 0,
    cursor: { x: segments[0].x1, y: segments[0].y1 },
  };
}

function segmentLength(seg: SimSegment): number {
  return Math.hypot(seg.x2 - seg.x1, seg.y2 - seg.y1);
}

/** Komut metninden PEN UP/DOWN + MOVE segmentleri üretir. */
export function parseCommandsToSegments(text: string): SimSegment[] {
  const segments: SimSegment[] = [];
  let x = 0;
  let y = 0;
  let penDown = false;

  for (const raw of text.split("\n")) {
    const line = raw.trim();
    if (!line) continue;
    const upper = line.toUpperCase();
    if (upper === "PEN DOWN") {
      penDown = true;
      continue;
    }
    if (upper === "PEN UP") {
      penDown = false;
      continue;
    }
    if (upper === "BEGIN" || upper === "END") continue;

    const moveMatch = line.match(/^MOVE\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)/i);
    if (!moveMatch) continue;

    const nx = Number(moveMatch[1]);
    const ny = Number(moveMatch[2]);
    if (!Number.isFinite(nx) || !Number.isFinite(ny)) continue;

    if (nx !== x || ny !== y) {
      segments.push({
        x1: x,
        y1: y,
        x2: nx,
        y2: ny,
        kind: penDown ? "draw" : "travel",
      });
    }
    x = nx;
    y = ny;
  }

  return segments;
}

/** pathPoints yalnızca yedek: tüm segmentler çizim kabul edilir. */
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

/** Önce komut metni, yoksa pathPoints kullanılır. */
export function buildSimulationSegments(commandsText: string, pathPoints: number[][]): SimSegment[] {
  const fromCommands = parseCommandsToSegments(commandsText);
  if (fromCommands.length > 0) return fromCommands;
  return pathPointsToSegments(pathPoints);
}

export function tickPlayback(
  state: SimPlayback,
  segments: SimSegment[],
  dtMs: number,
  mmPerSec = 600,
): SimPlayback {
  if (!state.active || state.completed || !segments.length) return state;

  let dist = (mmPerSec * dtMs) / 1000;
  let segIdx = state.segmentIndex;
  let t = state.segmentT;

  const totalLen = segments.reduce((sum, s) => sum + Math.max(segmentLength(s), 1e-9), 0);

  while (dist > 0 && segIdx < segments.length) {
    const seg = segments[segIdx];
    const len = Math.max(segmentLength(seg), 1e-9);
    const left = len * (1 - t);
    if (dist >= left) {
      dist -= left;
      segIdx += 1;
      t = 0;
    } else {
      t += dist / len;
      dist = 0;
    }
  }

  if (segIdx >= segments.length) {
    const last = segments[segments.length - 1];
    return {
      ...state,
      active: false,
      completed: true,
      progress: 100,
      segmentIndex: segments.length,
      segmentT: 1,
      cursor: { x: last.x2, y: last.y2 },
    };
  }

  const seg = segments[segIdx];
  const cursor = {
    x: seg.x1 + (seg.x2 - seg.x1) * t,
    y: seg.y1 + (seg.y2 - seg.y1) * t,
  };

  let traveled = 0;
  for (let i = 0; i < segIdx; i++) traveled += Math.max(segmentLength(segments[i]), 1e-9);
  traveled += Math.max(segmentLength(seg), 1e-9) * t;
  const progress = totalLen > 0 ? Math.min(100, (traveled / totalLen) * 100) : 100;

  return { ...state, progress, segmentIndex: segIdx, segmentT: t, cursor };
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
