import React, { useState } from "react";

function Accordion({ title, subtitle, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div
      style={{
        border: "1px solid #333",
        borderRadius: 12,
        padding: 12,
        background: "#151515",
        boxShadow: "0 10px 25px rgba(0,0,0,0.45)"
      }}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 8,
          background: "transparent",
          border: "none",
          padding: 0,
          color: "#eee",
          cursor: "pointer"
        }}
      >
        <div>
          <div style={{ fontWeight: 800, fontSize: 14 }}>{title}</div>
          {subtitle ? <div style={{ fontSize: 11, opacity: 0.7, marginTop: 2 }}>{subtitle}</div> : null}
        </div>
        <span style={{ fontSize: 16 }}>{open ? "▾" : "▸"}</span>
      </button>
      {open && <div style={{ marginTop: 10, fontSize: 12 }}>{children}</div>}
    </div>
  );
}

export default function PlanStatisticsPanel({ dxfInsight }) {
  if (!dxfInsight) return null;
  const supported = dxfInsight.entity_counts_supported ?? {};
  const unsupported = dxfInsight.entity_counts_unsupported ?? {};
  const supportedTotal = Object.values(supported).reduce((a, b) => a + b, 0);
  const unsupportedTotal = Object.values(unsupported).reduce((a, b) => a + b, 0);
  const reasons = dxfInsight.suggested_layers_reasons ?? [];
  const recommended = dxfInsight.recommended_action ?? "";

  return (
    <div style={{ marginTop: 8, padding: "8px 10px", background: "#0d1117", borderRadius: 8, border: "1px solid #30363d" }}>
      <div style={{ fontWeight: 700, marginBottom: 6, fontSize: 12 }}>Plan İstatistikleri</div>
      <div style={{ fontSize: 11, marginBottom: 4 }}>
        <span style={{ color: "#22c55e" }}>Desteklenen: {supportedTotal}</span>
        {Object.entries(supported).length > 0 && (
          <span style={{ opacity: 0.8, marginLeft: 4 }}>
            ({Object.entries(supported).map(([k, v]) => `${k}:${v}`).join(", ")})
          </span>
        )}
      </div>
      {unsupportedTotal > 0 && (
        <div style={{ fontSize: 11, marginBottom: 4, color: "#eab308" }}>
          Desteklenmeyen: {unsupportedTotal}
          {Object.entries(unsupported).length > 0 && (
            <span style={{ opacity: 0.8, marginLeft: 4 }}>
              ({Object.entries(unsupported).map(([k, v]) => `${k}:${v}`).join(", ")})
            </span>
          )}
        </div>
      )}
      {reasons.length > 0 && (
        <div style={{ fontSize: 11, marginBottom: 4, opacity: 0.9 }}>
          Önerilen katman gerekçeleri: {reasons.slice(0, 3).map((r) => `${r.layer}: ${r.reason}`).join("; ")}
        </div>
      )}
      {recommended && (
        <div style={{ fontSize: 11, color: "#58a6ff", marginTop: 4 }}>{recommended}</div>
      )}
      <Accordion title="Detaylar" subtitle="Entity örnekleri, uyarı kodları" defaultOpen={false}>
        <div style={{ fontSize: 10 }}>
          {dxfInsight.unsupported_samples?.length > 0 && (
            <div style={{ marginBottom: 6 }}>
              <b>Atlanan örnekler:</b>
              <ul style={{ margin: "2px 0 0 16px", padding: 0 }}>
                {(dxfInsight.unsupported_samples || []).slice(0, 5).map((s, i) => (
                  <li key={i}>{s.type} (katman: {s.layer}) — {s.note}</li>
                ))}
              </ul>
            </div>
          )}
          {dxfInsight.warning_codes?.length > 0 && (
            <div>
              <b>Uyarı kodları:</b> {(dxfInsight.warning_codes || []).join(", ")}
            </div>
          )}
        </div>
      </Accordion>
    </div>
  );
}
