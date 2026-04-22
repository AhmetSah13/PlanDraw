import React from "react";

export default function PlanSourceSelector({ selectedSource, onChange }) {
  const base = { padding: "6px 12px", borderRadius: 8, border: "1px solid #444", background: "#222", color: "#eee", cursor: "pointer", fontSize: 13 };
  const active = { ...base, background: "#1d3b7a" };
  return (
    <div style={{ display: "flex", gap: 4, marginBottom: 12 }}>
      <button type="button" style={selectedSource === "dxf" ? active : base} onClick={() => onChange("dxf")}>DXF</button>
      <button type="button" style={selectedSource === "dwg" ? active : base} onClick={() => onChange("dwg")}>DWG</button>
      <button type="button" style={selectedSource === "json" ? active : base} onClick={() => onChange("json")}>JSON</button>
      <button type="button" style={selectedSource === "manual" ? active : base} onClick={() => onChange("manual")}>Manuel (LINE)</button>
    </div>
  );
}
