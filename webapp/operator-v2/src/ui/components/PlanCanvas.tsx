import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";

type Point = [number, number];
type WallSegment = [number, number, number, number];

interface MarkerPoint {
  x: number;
  y: number;
  color: string;
  radius?: number;
}

interface Props {
  pathPoints?: number[][];
  walls?: number[][];
  prePathPoints?: number[][];
  postPathPoints?: number[][];
  markers?: MarkerPoint[];
  progress?: number;
  showGrid?: boolean;
  height?: number;
  testId?: string;
}

interface Viewport {
  scale: number;
  offsetX: number;
  offsetY: number;
}

const EMPTY_MARKERS: MarkerPoint[] = [];

function toPoints(values?: number[][]): Point[] {
  if (!Array.isArray(values)) {
    return [];
  }
  return values
    .filter((value) => Array.isArray(value) && value.length >= 2)
    .map((value) => [Number(value[0]), Number(value[1])] as Point)
    .filter((value) => Number.isFinite(value[0]) && Number.isFinite(value[1]));
}

function toWalls(values?: number[][]): WallSegment[] {
  if (!Array.isArray(values)) {
    return [];
  }
  return values
    .filter((value) => Array.isArray(value) && value.length >= 4)
    .map((value) => [Number(value[0]), Number(value[1]), Number(value[2]), Number(value[3])] as WallSegment)
    .filter((value) => value.every((entry) => Number.isFinite(entry)));
}

function clampProgress(value?: number) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return 1;
  }
  return Math.max(0, Math.min(1, value));
}

function collectBounds(
  paths: Point[][],
  walls: WallSegment[],
  markers: MarkerPoint[],
): { minX: number; minY: number; maxX: number; maxY: number } | null {
  let minX = Number.POSITIVE_INFINITY;
  let minY = Number.POSITIVE_INFINITY;
  let maxX = Number.NEGATIVE_INFINITY;
  let maxY = Number.NEGATIVE_INFINITY;

  for (const path of paths) {
    for (const [x, y] of path) {
      minX = Math.min(minX, x);
      minY = Math.min(minY, y);
      maxX = Math.max(maxX, x);
      maxY = Math.max(maxY, y);
    }
  }

  for (const [x1, y1, x2, y2] of walls) {
    minX = Math.min(minX, x1, x2);
    minY = Math.min(minY, y1, y2);
    maxX = Math.max(maxX, x1, x2);
    maxY = Math.max(maxY, y1, y2);
  }

  for (const marker of markers) {
    minX = Math.min(minX, marker.x);
    minY = Math.min(minY, marker.y);
    maxX = Math.max(maxX, marker.x);
    maxY = Math.max(maxY, marker.y);
  }

  if (!Number.isFinite(minX) || !Number.isFinite(minY) || !Number.isFinite(maxX) || !Number.isFinite(maxY)) {
    return null;
  }

  if (minX === maxX) {
    maxX += 1;
  }
  if (minY === maxY) {
    maxY += 1;
  }

  return { minX, minY, maxX, maxY };
}

function drawPath(ctx: CanvasRenderingContext2D, points: Point[], color: string, lineWidth: number, dashed = false) {
  if (points.length < 2) {
    return;
  }

  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineWidth = lineWidth;
  ctx.setLineDash(dashed ? [8, 6] : []);
  ctx.beginPath();
  ctx.moveTo(points[0][0], points[0][1]);
  for (let i = 1; i < points.length; i += 1) {
    ctx.lineTo(points[i][0], points[i][1]);
  }
  ctx.stroke();
  ctx.restore();
}

function partialPath(points: Point[], progress: number): Point[] {
  if (points.length < 2) {
    return points;
  }
  if (progress <= 0) {
    return [points[0]];
  }
  if (progress >= 1) {
    return points;
  }

  const lengths: number[] = [];
  let total = 0;
  for (let i = 1; i < points.length; i += 1) {
    const dx = points[i][0] - points[i - 1][0];
    const dy = points[i][1] - points[i - 1][1];
    const len = Math.hypot(dx, dy);
    lengths.push(len);
    total += len;
  }
  if (total <= 0) {
    return points;
  }

  const target = total * progress;
  const result: Point[] = [points[0]];
  let accumulated = 0;

  for (let i = 1; i < points.length; i += 1) {
    const segLen = lengths[i - 1];
    if (accumulated + segLen <= target) {
      result.push(points[i]);
      accumulated += segLen;
      continue;
    }

    const remain = target - accumulated;
    const t = segLen <= 0 ? 0 : remain / segLen;
    result.push([
      points[i - 1][0] + (points[i][0] - points[i - 1][0]) * t,
      points[i - 1][1] + (points[i][1] - points[i - 1][1]) * t,
    ]);
    break;
  }

  return result;
}

export function PlanCanvas({
  pathPoints,
  walls,
  prePathPoints,
  postPathPoints,
  markers,
  progress = 1,
  showGrid = true,
  height = 320,
  testId,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const dragRef = useRef<{ startX: number; startY: number; active: boolean }>({
    startX: 0,
    startY: 0,
    active: false,
  });

  const [viewport, setViewport] = useState<Viewport>({ scale: 1, offsetX: 0, offsetY: 0 });

  const markerList = markers ?? EMPTY_MARKERS;

  const applyZoom = useCallback((clientX: number, clientY: number, deltaY: number) => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }
    const rect = canvas.getBoundingClientRect();
    const mouseX = clientX - rect.left;
    const mouseY = clientY - rect.top;

    setViewport((current) => {
      const factor = deltaY < 0 ? 1.08 : 0.92;
      const nextScale = Math.max(0.2, Math.min(40, current.scale * factor));
      const scaleRatio = nextScale / current.scale;
      return {
        scale: nextScale,
        offsetX: mouseX - (mouseX - current.offsetX) * scaleRatio,
        offsetY: mouseY - (mouseY - current.offsetY) * scaleRatio,
      };
    });
  }, []);

  const prepared = useMemo(() => {
    return {
      mainPath: toPoints(pathPoints),
      prePath: toPoints(prePathPoints),
      postPath: toPoints(postPathPoints),
      wallSegments: toWalls(walls),
    };
  }, [pathPoints, prePathPoints, postPathPoints, walls]);

  const bounds = useMemo(
    () => collectBounds([prepared.mainPath, prepared.prePath, prepared.postPath], prepared.wallSegments, markerList),
    [markerList, prepared],
  );

  useEffect(() => {
    const wrapper = wrapperRef.current;
    if (!wrapper) {
      return;
    }

    const onWheelCapture = (event: WheelEvent) => {
      if (!wrapper.contains(event.target as Node)) {
        return;
      }
      if (event.cancelable) {
        event.preventDefault();
      }
      event.stopPropagation();
      applyZoom(event.clientX, event.clientY, event.deltaY);
    };

    document.addEventListener("wheel", onWheelCapture, { passive: false, capture: true });
    return () => {
      document.removeEventListener("wheel", onWheelCapture, true);
    };
  }, [applyZoom]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrapper = wrapperRef.current;
    if (!canvas || !wrapper || !bounds) {
      return;
    }

    const rect = wrapper.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.max(1, Math.floor(rect.width * dpr));
    canvas.height = Math.max(1, Math.floor(height * dpr));
    canvas.style.width = `${rect.width}px`;
    canvas.style.height = `${height}px`;

    const width = rect.width;
    const dataWidth = bounds.maxX - bounds.minX;
    const dataHeight = bounds.maxY - bounds.minY;
    const fitScale = Math.min((width - 24) / dataWidth, (height - 24) / dataHeight);
    const clamped = Number.isFinite(fitScale) && fitScale > 0 ? fitScale : 1;

    setViewport({
      scale: clamped,
      offsetX: (width - dataWidth * clamped) / 2 - bounds.minX * clamped,
      offsetY: (height - dataHeight * clamped) / 2 - bounds.minY * clamped,
    });
  }, [bounds, height]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }
    const ctx = canvas.getContext("2d");
    if (!ctx) {
      return;
    }

    const dpr = window.devicePixelRatio || 1;
    const width = canvas.width / dpr;
    const h = canvas.height / dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, h);

    if (!bounds) {
      ctx.fillStyle = "#5f6f87";
      ctx.font = "14px Segoe UI";
      ctx.fillText("Önizleme için veri bekleniyor.", 20, 32);
      return;
    }

    ctx.save();
    ctx.translate(viewport.offsetX, viewport.offsetY);
    ctx.scale(viewport.scale, viewport.scale);

    if (showGrid) {
      const gridStep = 1;
      const minX = Math.floor(bounds.minX / gridStep) * gridStep;
      const maxX = Math.ceil(bounds.maxX / gridStep) * gridStep;
      const minY = Math.floor(bounds.minY / gridStep) * gridStep;
      const maxY = Math.ceil(bounds.maxY / gridStep) * gridStep;
      ctx.strokeStyle = "rgba(120, 140, 168, 0.15)";
      ctx.lineWidth = 0.02;
      for (let x = minX; x <= maxX; x += gridStep) {
        ctx.beginPath();
        ctx.moveTo(x, minY);
        ctx.lineTo(x, maxY);
        ctx.stroke();
      }
      for (let y = minY; y <= maxY; y += gridStep) {
        ctx.beginPath();
        ctx.moveTo(minX, y);
        ctx.lineTo(maxX, y);
        ctx.stroke();
      }
    }

    for (const segment of prepared.wallSegments) {
      ctx.strokeStyle = "#1e334f";
      ctx.lineWidth = 0.08;
      ctx.setLineDash([]);
      ctx.beginPath();
      ctx.moveTo(segment[0], segment[1]);
      ctx.lineTo(segment[2], segment[3]);
      ctx.stroke();
    }

    drawPath(ctx, prepared.prePath, "#a0aab9", 0.07, true);
    drawPath(ctx, prepared.postPath, "#1f63b6", 0.1, false);

    const visiblePath = partialPath(prepared.mainPath, clampProgress(progress));
    drawPath(ctx, visiblePath, "#6f7c8e", 0.09, false);

    if (visiblePath.length > 0) {
      const head = visiblePath[visiblePath.length - 1];
      ctx.fillStyle = "#1f63b6";
      ctx.beginPath();
      ctx.arc(head[0], head[1], 0.18, 0, Math.PI * 2);
      ctx.fill();
    }

    ctx.fillStyle = "#17365f";
    ctx.beginPath();
    ctx.arc(0, 0, 0.15, 0, Math.PI * 2);
    ctx.fill();

    for (const marker of markerList) {
      ctx.fillStyle = marker.color;
      ctx.beginPath();
      ctx.arc(marker.x, marker.y, marker.radius ?? 0.16, 0, Math.PI * 2);
      ctx.fill();
    }

    ctx.restore();
  }, [bounds, markerList, prepared, progress, showGrid, viewport]);

  const handlePointerDown = (event: React.PointerEvent<HTMLCanvasElement>) => {
    dragRef.current = { startX: event.clientX, startY: event.clientY, active: true };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const handlePointerMove = (event: React.PointerEvent<HTMLCanvasElement>) => {
    if (!dragRef.current.active) {
      return;
    }
    const dx = event.clientX - dragRef.current.startX;
    const dy = event.clientY - dragRef.current.startY;
    dragRef.current.startX = event.clientX;
    dragRef.current.startY = event.clientY;
    setViewport((current) => ({
      ...current,
      offsetX: current.offsetX + dx,
      offsetY: current.offsetY + dy,
    }));
  };

  const handlePointerUp = () => {
    dragRef.current.active = false;
  };

  return (
    <div className="plan-canvas" ref={wrapperRef}>
      <canvas
        ref={canvasRef}
        data-testid={testId}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
      />
    </div>
  );
}

