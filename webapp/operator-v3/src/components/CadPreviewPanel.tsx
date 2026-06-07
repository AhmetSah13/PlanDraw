import { useEffect, useRef } from "react";
import { Crosshair, Grid3X3 } from "lucide-react";
import { tr } from "../content/tr";
import { GlowCard } from "./GlowCard";

interface CadPreviewPanelProps {
  planName: string | null;
  points: number[][];
  strokeCount: number;
}

export function CadPreviewPanel({ planName, points, strokeCount }: CadPreviewPanelProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const hasPath = points.length >= 2;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

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

    if (!hasPath) return;

    const xs = points.map((p) => p[0]);
    const ys = points.map((p) => p[1]);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const pad = 36;
    const spanX = Math.max(maxX - minX, 1e-6);
    const spanY = Math.max(maxY - minY, 1e-6);
    const scale = Math.min((w - pad * 2) / spanX, (h - pad * 2) / spanY);
    const toX = (x: number) => pad + (x - minX) * scale;
    const toY = (y: number) => h - pad - (y - minY) * scale;

    const gradient = ctx.createLinearGradient(0, 0, w, h);
    gradient.addColorStop(0, "#22D3EE");
    gradient.addColorStop(1, "#6366F1");
    ctx.strokeStyle = gradient;
    ctx.lineWidth = 2.5;
    ctx.shadowColor = "rgba(34, 211, 238, 0.5)";
    ctx.shadowBlur = 8;
    ctx.beginPath();
    ctx.moveTo(toX(points[0][0]), toY(points[0][1]));
    for (let i = 1; i < points.length; i++) {
      ctx.lineTo(toX(points[i][0]), toY(points[i][1]));
    }
    ctx.stroke();
    ctx.shadowBlur = 0;

    for (const [x, y] of points) {
      ctx.fillStyle = "#38BDF8";
      ctx.beginPath();
      ctx.arc(toX(x), toY(y), 3, 0, Math.PI * 2);
      ctx.fill();
    }
  }, [points, hasPath]);

  return (
    <GlowCard
      title={tr.preview.title}
      subtitle={planName ?? tr.preview.waiting}
      className="min-h-[320px] flex-1"
      accent
    >
      <div className="relative overflow-hidden rounded-xl border border-cyan-500/15 bg-[#030712]">
        <div className="absolute inset-0 bg-grid-pattern bg-grid opacity-60" />
        {hasPath ? (
          <canvas ref={canvasRef} width={640} height={360} className="relative z-10 h-auto w-full" />
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
        <div className="absolute bottom-3 left-3 z-20 flex items-center gap-3 text-[10px] text-slate-500">
          <Crosshair className="h-3 w-3 text-cyan-600" />
          <span>
            {tr.preview.points}: {points.length} · Stroke: {strokeCount}
          </span>
        </div>
      </div>
    </GlowCard>
  );
}
