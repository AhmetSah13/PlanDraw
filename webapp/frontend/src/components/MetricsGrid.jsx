/**
 * MetricsGrid — move_count, path_length, estimated_time, collision_count (opsiyonel overlap/touch)
 */
import React from "react";

function fmtNum(v, frac = 1) {
  if (v == null || !Number.isFinite(v)) return "—";
  return Number(v).toFixed(frac);
}

export default function MetricsGrid({ stats, collisionCount, showDebugCounts = false }) {
  if (!stats) {
    return (
      <div style={{ fontSize: 13, opacity: 0.7 }}>Metrik yok. Önce planı içe aktarıp analiz edin.</div>
    );
  }
  const gridStyle = {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
    gap: 10,
  };
  const cellStyle = {
    padding: "8px 10px",
    borderRadius: 8,
    border: "1px solid #333",
    background: "#111",
    fontSize: 12,
  };
  const labelStyle = { opacity: 0.8, marginBottom: 2 };
  const valueStyle = { fontWeight: 700, fontSize: 14 };

  return (
    <div style={gridStyle}>
      <div style={cellStyle}>
        <div style={labelStyle}>Hareket sayısı</div>
        <div style={valueStyle}>{stats.move_count ?? "—"}</div>
      </div>
      <div style={cellStyle}>
        <div style={labelStyle}>Yol uzunluğu</div>
        <div style={valueStyle}>{fmtNum(stats.path_length)}</div>
      </div>
      <div style={cellStyle}>
        <div style={labelStyle}>Tahmini süre</div>
        <div style={valueStyle}>{fmtNum(stats.estimated_time)} s</div>
      </div>
      <div style={cellStyle}>
        <div style={labelStyle}>Kesişim (beklenmeyen)</div>
        <div style={valueStyle}>{collisionCount ?? stats.collision_count ?? 0}</div>
      </div>
      {showDebugCounts && (
        <>
          <div style={cellStyle}>
            <div style={labelStyle}>Overlap (duvar üstü)</div>
            <div style={valueStyle}>{stats.wall_overlap_count ?? 0}</div>
          </div>
          <div style={cellStyle}>
            <div style={labelStyle}>Touch</div>
            <div style={valueStyle}>{stats.wall_touch_count ?? 0}</div>
          </div>
        </>
      )}
    </div>
  );
}
