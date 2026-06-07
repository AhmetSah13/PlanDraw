import { useEffect, useRef } from "react";
import { tr } from "../content/tr";

interface PlanPreviewPanelProps {
  planName: string | null;
  pointCount: number;
  strokeCount: number;
  points: number[][];
}

export function PlanPreviewPanel({
  planName,
  pointCount,
  strokeCount,
  points,
}: PlanPreviewPanelProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || points.length < 2) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    const xs = points.map((p) => p[0]);
    const ys = points.map((p) => p[1]);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const pad = 20;
    const spanX = Math.max(maxX - minX, 1e-6);
    const spanY = Math.max(maxY - minY, 1e-6);
    const scale = Math.min((w - pad * 2) / spanX, (h - pad * 2) / spanY);

    const toX = (x: number) => pad + (x - minX) * scale;
    const toY = (y: number) => h - pad - (y - minY) * scale;

    ctx.strokeStyle = "#0B6E99";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(toX(points[0][0]), toY(points[0][1]));
    for (let i = 1; i < points.length; i++) {
      ctx.lineTo(toX(points[i][0]), toY(points[i][1]));
    }
    ctx.stroke();

    ctx.fillStyle = "#38BDF8";
    for (const [x, y] of points) {
      ctx.beginPath();
      ctx.arc(toX(x), toY(y), 2.5, 0, Math.PI * 2);
      ctx.fill();
    }
  }, [points]);

  return (
    <section className="panel">
      <h2 className="text-lg font-semibold text-slate-900">{tr.preview.title}</h2>
      <p className="mt-1 text-sm text-slate-600">
        {planName ?? "—"} · {tr.preview.points}: {pointCount} · Stroke: {strokeCount}
      </p>

      <div className="mt-4 overflow-hidden rounded-xl border border-slate-200 bg-slate-50">
        {points.length >= 2 ? (
          <canvas ref={canvasRef} width={480} height={280} className="h-auto w-full" />
        ) : (
          <div className="flex h-48 items-center justify-center px-4 text-center text-sm text-slate-500">
            {tr.preview.placeholder}
          </div>
        )}
      </div>
    </section>
  );
}
