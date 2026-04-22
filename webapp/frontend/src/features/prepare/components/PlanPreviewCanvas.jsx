import React, { useCallback, useEffect, useRef, useState } from "react";
import "./PlanPreviewCanvas.css";

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

function computeBoundsFromData(walls, rawPath) {
  const pts = [];
  walls.forEach((w) => {
    if (w.length >= 4) {
      pts.push(w[0], w[1]);
      pts.push(w[2], w[3]);
    }
  });
  rawPath.forEach((p) => {
    if (p.length >= 2) pts.push(p[0], p[1]);
  });
  if (pts.length < 2) return null;
  let minx = pts[0],
    maxx = pts[0],
    miny = pts[1],
    maxy = pts[1];
  for (let i = 0; i < pts.length; i += 2) {
    const x = pts[i],
      y = pts[i + 1];
    if (x < minx) minx = x;
    if (x > maxx) maxx = x;
    if (y < miny) miny = y;
    if (y > maxy) maxy = y;
  }
  return [minx, miny, maxx, maxy];
}

/**
 * Duvarlar + ham yol + başlangıç noktası önizlemesi (legacy çizim adımıyla uyumlu koordinat dönüşümü).
 */
export default function PlanPreviewCanvas({ walls, rawPath, startPoint, onStartPointChange }) {
  const canvasRef = useRef(null);
  const boundsRef = useRef(null);
  const viewRef = useRef(resetView(600, 400));
  const panStartRef = useRef(null);
  const skippedClickRef = useRef(false);

  const [showWalls, setShowWalls] = useState(true);
  const [showPath, setShowPath] = useState(true);

  const worldToScreen = useCallback((x, y) => {
    const v = viewRef.current;
    return {
      sx: x * v.scale + v.offsetX,
      sy: -y * v.scale + v.offsetY,
    };
  }, []);

  const screenToWorld = useCallback((sx, sy) => {
    const v = viewRef.current;
    return {
      x: (sx - v.offsetX) / v.scale,
      y: -(sy - v.offsetY) / v.scale,
    };
  }, []);

  const redraw = useCallback(() => {
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
      walls.forEach((seg) => {
        if (seg.length >= 4) {
          const a = worldToScreen(seg[0], seg[1]);
          const b = worldToScreen(seg[2], seg[3]);
          ctx.moveTo(a.sx, a.sy);
          ctx.lineTo(b.sx, b.sy);
        }
      });
      ctx.stroke();
    }
    if (showPath && rawPath.length > 1) {
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
  }, [worldToScreen, showWalls, showPath, walls, rawPath, startPoint]);

  useEffect(() => {
    boundsRef.current = computeBoundsFromData(walls, rawPath);
  }, [walls, rawPath]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const w = canvas.width;
    const h = canvas.height;
    viewRef.current = computeFitView(boundsRef.current, w, h, MARGIN);
    redraw();
  }, [walls, rawPath, redraw]);

  useEffect(() => {
    redraw();
  }, [startPoint, showWalls, showPath, redraw]);

  const handleFit = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    viewRef.current = computeFitView(boundsRef.current, canvas.width, canvas.height, MARGIN);
    redraw();
  }, [redraw]);

  const handleResetView = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    viewRef.current = resetView(canvas.width, canvas.height);
    redraw();
  }, [redraw]);

  return (
    <div className="plan-preview">
      <div className="plan-preview__toolbar">
        <label className="plan-preview__chk">
          <input type="checkbox" checked={showWalls} onChange={(e) => setShowWalls(e.target.checked)} />
          <span>Duvarlar</span>
        </label>
        <label className="plan-preview__chk">
          <input type="checkbox" checked={showPath} onChange={(e) => setShowPath(e.target.checked)} />
          <span>Ham yol</span>
        </label>
        <button type="button" className="plan-preview__btn" onClick={handleFit}>
          Sığdır
        </button>
        <button type="button" className="plan-preview__btn" onClick={handleResetView}>
          Görünüm sıfırla
        </button>
      </div>
      <p className="plan-preview__hint">Başlangıç: tıklayın · Pan: sürükleyin · Zoom: tekerlek</p>
      <canvas
        ref={canvasRef}
        className="plan-preview__canvas"
        width={600}
        height={400}
        role="img"
        aria-label="Plan önizlemesi"
        onClick={(e) => {
          if (skippedClickRef.current) {
            skippedClickRef.current = false;
            return;
          }
          const canvas = canvasRef.current;
          if (!canvas || !onStartPointChange) return;
          const rect = canvas.getBoundingClientRect();
          const sx = (e.clientX - rect.left) * (canvas.width / rect.width);
          const sy = (e.clientY - rect.top) * (canvas.height / rect.height);
          const { x, y } = screenToWorld(sx, sy);
          onStartPointChange([x, y]);
        }}
        onMouseDown={(e) => {
          const canvas = canvasRef.current;
          if (!canvas) return;
          const rect = canvas.getBoundingClientRect();
          const sx = (e.clientX - rect.left) * (canvas.width / rect.width);
          const sy = (e.clientY - rect.top) * (canvas.height / rect.height);
          panStartRef.current = {
            sx,
            sy,
            offsetX: viewRef.current.offsetX,
            offsetY: viewRef.current.offsetY,
            moved: false,
          };
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
            offsetY: panStartRef.current.offsetY + dy,
          };
          redraw();
        }}
        onMouseLeave={() => {
          panStartRef.current = null;
        }}
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
            offsetY: sy + pivot.y * newScale,
          };
          redraw();
        }}
      />
    </div>
  );
}
