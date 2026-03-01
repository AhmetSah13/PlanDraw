/**
 * StatusBanner — Aktif plan adı, step etiketi/değeri, seçili katman sayısı, opsiyonel stale badge
 */
import React from "react";

export default function StatusBanner({ planName, stepLabel, stepValue, layersCount, resultsStale }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        flexWrap: "wrap",
        padding: "8px 12px",
        background: "#111",
        borderRadius: 8,
        border: "1px solid #333",
        fontSize: 12,
        marginBottom: 12,
      }}
    >
      {planName && (
        <span style={{ color: "#94a3b8" }}>
          Plan: <strong style={{ color: "#eee" }}>{planName}</strong>
        </span>
      )}
      {(stepLabel != null || stepValue != null) && (
        <span style={{ color: "#94a3b8" }}>
          Adım: <strong style={{ color: "#eee" }}>{stepLabel ?? ""} {stepValue != null ? `(${Number(stepValue).toFixed(2)}m)` : ""}</strong>
        </span>
      )}
      {layersCount != null && layersCount > 0 && (
        <span style={{ color: "#94a3b8" }}>
          Katman: <strong style={{ color: "#eee" }}>{layersCount}</strong>
        </span>
      )}
      {resultsStale && (
        <span style={{ padding: "2px 8px", borderRadius: 6, background: "#422c02", color: "#fef08a", fontWeight: 600, fontSize: 11 }}>
          Sonuçlar güncelliğini yitirdi
        </span>
      )}
    </div>
  );
}
