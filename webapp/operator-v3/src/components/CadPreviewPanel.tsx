import { useEffect, useMemo, useRef } from "react";
import { Crosshair, Grid3X3, PlayCircle } from "lucide-react";
import { tr } from "../content/tr";
import {
  buildSimulationSegments,
  collectBoundsFromSegments,
  createViewportTransform,
  tickPlayback,
  type SimPlayback,
  type SimSegment,
  type ViewportTransform,
} from "../lib/commandSimulation";
import { cn } from "../lib/cn";
import { GlowCard } from "./GlowCard";

const CANVAS_W = 640;
const CANVAS_H = 360;

interface CadPreviewPanelProps {
  planName: string | null;
  points: number[][];
  strokeCount: number;
  commandsText: string;
  simPlayback: SimPlayback;
  simJobId: string | null;
  onPlaybackUpdate: (next: SimPlayback) => void;
  onSimulationComplete: () => void;
}

function drawGrid(ctx: CanvasRenderingContext2D, w: number, h: number) {
  ctx.strokeStyle = "rgba(34, 211, 238, 0.08)";
  ctx.lineWidth = 1;
  const grid = 24;
  for (let x = 0; x <= w; x += grid) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
    ctx.stroke();
  }
  for (let y = 0; y <= h; y += grid) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }
  ctx.strokeStyle = "rgba(99, 102, 241, 0.35)";
  ctx.setLineDash([4, 4]);
  ctx.beginPath();
  ctx.moveTo(w / 2, 0);
  ctx.lineTo(w / 2, h);
  ctx.moveTo(0, h / 2);
  ctx.lineTo(w, h / 2);
  ctx.stroke();
  ctx.setLineDash([]);
}

function drawSegment(
  ctx: CanvasRenderingContext2D,
  seg: SimSegment,
  vp: ViewportTransform,
  alpha = 1,
  partialT = 1,
) {
  const x2 = seg.x1 + (seg.x2 - seg.x1) * partialT;
  const y2 = seg.y1 + (seg.y2 - seg.y1) * partialT;
  const isDraw = seg.kind === "draw";

  ctx.globalAlpha = alpha;
  if (isDraw) {
    const gradient = ctx.createLinearGradient(vp.toX(seg.x1), vp.toY(seg.y1), vp.toX(x2), vp.toY(y2));
    gradient.addColorStop(0, "#22D3EE");
    gradient.addColorStop(1, "#34D399");
    ctx.strokeStyle = gradient;
    ctx.lineWidth = 2.5;
    ctx.setLineDash([]);
    ctx.shadowColor = "rgba(34, 211, 238, 0.45)";
    ctx.shadowBlur = 6;
  } else {
    ctx.strokeStyle = "rgba(148, 163, 184, 0.45)";
    ctx.lineWidth = 1.5;
    ctx.setLineDash([6, 6]);
    ctx.shadowBlur = 0;
  }

  ctx.beginPath();
  ctx.moveTo(vp.toX(seg.x1), vp.toY(seg.y1));
  ctx.lineTo(vp.toX(x2), vp.toY(y2));
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.shadowBlur = 0;
  ctx.globalAlpha = 1;
}

function drawStaticPath(ctx: CanvasRenderingContext2D, points: number[][], vp: ViewportTransform) {
  const gradient = ctx.createLinearGradient(0, 0, CANVAS_W, CANVAS_H);
  gradient.addColorStop(0, "#22D3EE");
  gradient.addColorStop(1, "#6366F1");
  ctx.strokeStyle = gradient;
  ctx.lineWidth = 2.5;
  ctx.shadowColor = "rgba(34, 211, 238, 0.5)";
  ctx.shadowBlur = 8;
  ctx.beginPath();
  ctx.moveTo(vp.toX(points[0][0]), vp.toY(points[0][1]));
  for (let i = 1; i < points.length; i++) {
    ctx.lineTo(vp.toX(points[i][0]), vp.toY(points[i][1]));
  }
  ctx.stroke();
  ctx.shadowBlur = 0;
}

function drawRobotCursor(ctx: CanvasRenderingContext2D, x: number, y: number) {
  ctx.fillStyle = "#F8FAFC";
  ctx.strokeStyle = "#22D3EE";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.arc(x, y, 6, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = "#22D3EE";
  ctx.beginPath();
  ctx.arc(x, y, 2.5, 0, Math.PI * 2);
  ctx.fill();
}

export function CadPreviewPanel({
  planName,
  points,
  strokeCount,
  commandsText,
  simPlayback,
  simJobId,
  onPlaybackUpdate,
  onSimulationComplete,
}: CadPreviewPanelProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const segments = useMemo(
    () => buildSimulationSegments(commandsText, points),
    [commandsText, points],
  );
  const hasPath = points.length >= 2 || segments.length > 0;
  const simulating = simPlayback.active || simPlayback.completed;
  const boundsPoints = useMemo(
    () => (segments.length ? collectBoundsFromSegments(segments) : points),
    [segments, points],
  );
  const viewport = useMemo(
    () => createViewportTransform(boundsPoints, CANVAS_W, CANVAS_H),
    [boundsPoints],
  );

  const playbackRef = useRef(simPlayback);
  playbackRef.current = simPlayback;
  const completedRunRef = useRef(0);

  useEffect(() => {
    if (!simPlayback.active || !segments.length) return;

    let frame = 0;
    let last = performance.now();
    const loop = (now: number) => {
      const dt = now - last;
      last = now;
      const next = tickPlayback(playbackRef.current, segments, dt);
      playbackRef.current = next;
      onPlaybackUpdate(next);
      if (next.active) {
        frame = requestAnimationFrame(loop);
      }
    };
    frame = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(frame);
  }, [simPlayback.active, simPlayback.runId, segments, onPlaybackUpdate]);

  useEffect(() => {
    if (
      simPlayback.completed &&
      simPlayback.runId > 0 &&
      completedRunRef.current !== simPlayback.runId
    ) {
      completedRunRef.current = simPlayback.runId;
      onSimulationComplete();
    }
  }, [simPlayback.completed, simPlayback.runId, onSimulationComplete]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !viewport) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, CANVAS_W, CANVAS_H);
    drawGrid(ctx, CANVAS_W, CANVAS_H);

    if (simulating && segments.length) {
      for (let i = 0; i < simPlayback.segmentIndex; i++) {
        drawSegment(ctx, segments[i], viewport, simPlayback.completed ? 1 : 0.85);
      }
      if (simPlayback.segmentIndex < segments.length) {
        drawSegment(
          ctx,
          segments[simPlayback.segmentIndex],
          viewport,
          1,
          simPlayback.segmentT,
        );
      }
      drawRobotCursor(ctx, viewport.toX(simPlayback.cursor.x), viewport.toY(simPlayback.cursor.y));
    } else if (points.length >= 2) {
      drawStaticPath(ctx, points, viewport);
      for (const [x, y] of points) {
        ctx.fillStyle = "#38BDF8";
        ctx.beginPath();
        ctx.arc(viewport.toX(x), viewport.toY(y), 3, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }, [points, segments, simulating, simPlayback, viewport]);

  const statusLabel = simPlayback.completed
    ? tr.preview.simCompleted
    : simPlayback.active
      ? tr.preview.simRunning
      : null;

  return (
    <GlowCard
      title={tr.preview.title}
      subtitle={planName ?? tr.preview.waiting}
      className="min-h-[320px] flex-1"
      accent
    >
      {simulating ? (
        <p className="mb-3 text-[11px] leading-relaxed text-amber-200/75">{tr.preview.simDisclaimer}</p>
      ) : null}

      <div className="relative overflow-hidden rounded-xl border border-cyan-500/15 bg-[#030712]">
        <div className="absolute inset-0 bg-grid-pattern bg-grid opacity-60" />
        {hasPath ? (
          <canvas
            ref={canvasRef}
            width={CANVAS_W}
            height={CANVAS_H}
            className="relative z-10 h-auto w-full"
          />
        ) : (
          <div className="relative z-10 flex min-h-[280px] flex-col items-center justify-center gap-4 p-8 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-cyan-500/20 bg-cyan-500/5">
              <Grid3X3 className="h-8 w-8 text-cyan-500/50" />
            </div>
            <div>
              <p className="text-sm font-medium text-slate-400">{tr.preview.waiting}</p>
              <p className="mt-1 text-xs text-slate-600">{tr.preview.hint}</p>
            </div>
          </div>
        )}

        {simulating ? (
          <div className="absolute right-3 top-3 z-20 rounded-lg border border-cyan-500/25 bg-slate-950/85 px-3 py-2 text-[10px] text-slate-300 backdrop-blur-sm">
            <div className="flex items-center gap-2 font-medium text-cyan-300">
              <PlayCircle className="h-3.5 w-3.5" />
              {statusLabel}
            </div>
            <p className="mt-1">
              {tr.preview.simProgress}: {Math.round(simPlayback.progress)}%
            </p>
            {simJobId ? (
              <p className="mt-0.5 truncate text-slate-500">
                {tr.preview.simJob}: {simJobId.slice(0, 12)}…
              </p>
            ) : null}
          </div>
        ) : null}

        <div className="absolute bottom-3 left-3 z-20 flex flex-wrap items-center gap-3 text-[10px] text-slate-500">
          <Crosshair className="h-3 w-3 text-cyan-600" />
          <span>
            {tr.preview.points}: {points.length} · Stroke: {strokeCount}
          </span>
          {simulating ? (
            <>
              <span className="text-slate-600">·</span>
              <span className="text-slate-500">{tr.preview.travelLegend}</span>
              <span className="inline-block h-0.5 w-4 border-t border-dashed border-slate-500" />
              <span className="text-emerald-400/90">{tr.preview.drawLegend}</span>
              <span className="inline-block h-0.5 w-4 bg-gradient-to-r from-cyan-400 to-emerald-400" />
            </>
          ) : null}
        </div>

        {simulating ? (
          <div className="absolute bottom-0 left-0 right-0 z-20 h-1 bg-slate-800">
            <div
              className={cn(
                "h-full transition-all duration-75",
                simPlayback.completed ? "bg-emerald-500" : "bg-cyan-500",
              )}
              style={{ width: `${simPlayback.progress}%` }}
            />
          </div>
        ) : null}
      </div>
    </GlowCard>
  );
}
