/**
 * AdvancedAccordion — Gelişmiş ayarlar (varsayılan kapalı)
 */
import React, { useState } from "react";

export default function AdvancedAccordion({ title, subtitle, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div
      style={{
        border: "1px solid #333",
        borderRadius: 12,
        padding: 12,
        background: "#151515",
        marginTop: 12,
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
          color: "#aaa",
          cursor: "pointer",
          fontSize: 13,
        }}
      >
        <span>
          <span style={{ fontWeight: 600 }}>{title}</span>
          {subtitle && <span style={{ marginLeft: 8, opacity: 0.8 }}>{subtitle}</span>}
        </span>
        <span>{open ? "▾" : "▸"}</span>
      </button>
      {open && <div style={{ marginTop: 10 }}>{children}</div>}
    </div>
  );
}
