import React, { useMemo } from "react";
import type { HizalamaKontrolNoktasi } from "../../workflow/store/workflowStore";
import { PlanCanvas } from "./PlanCanvas";

interface TransformData {
  theta_rad?: number;
  tx_m?: number;
  ty_m?: number;
}

interface Props {
  pathPoints: number[][];
  controlPoints: HizalamaKontrolNoktasi[];
  transform?: TransformData;
}

function applyTransform(path: number[][], transform?: TransformData) {
  if (!transform) {
    return path;
  }
  const theta = typeof transform.theta_rad === "number" ? transform.theta_rad : 0;
  const tx = typeof transform.tx_m === "number" ? transform.tx_m : 0;
  const ty = typeof transform.ty_m === "number" ? transform.ty_m : 0;
  const cos = Math.cos(theta);
  const sin = Math.sin(theta);

  return path.map((point) => {
    const x = Number(point[0]) || 0;
    const y = Number(point[1]) || 0;
    return [x * cos - y * sin + tx, x * sin + y * cos + ty];
  });
}

export function AlignmentOverlay({ pathPoints, controlPoints, transform }: Props) {
  const postPath = useMemo(() => applyTransform(pathPoints, transform), [pathPoints, transform]);
  const markers = useMemo(() => {
    const result: Array<{ x: number; y: number; color: string; radius?: number }> = [];
    for (const point of controlPoints) {
      result.push({ x: point.cad_x, y: point.cad_y, color: "#6b7280", radius: 0.16 });
      result.push({ x: point.site_x, y: point.site_y, color: "#1f63b6", radius: 0.16 });
    }
    return result;
  }, [controlPoints]);

  return (
    <PlanCanvas
      prePathPoints={pathPoints}
      postPathPoints={postPath}
      markers={markers}
      showGrid
      testId="alignment-overlay-canvas"
    />
  );
}

