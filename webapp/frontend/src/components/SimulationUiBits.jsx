import React from "react";

export function Badge({ ok, text }) {
  const style = {
    display: "inline-block",
    padding: "4px 10px",
    borderRadius: 999,
    fontSize: 12,
    border: "1px solid #333",
    background: ok ? "#103d25" : "#3d1010",
    color: "#fff",
    marginLeft: 8
  };
  return <span style={style}>{text}</span>;
}

export function DiagList({ title, items }) {
  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ fontWeight: 700, marginBottom: 6 }}>{title}</div>
      <div style={{ maxHeight: 220, overflow: "auto", border: "1px solid #333", borderRadius: 8, padding: 8 }}>
        {items.length === 0 ? (
          <div style={{ opacity: 0.7 }}>Yok</div>
        ) : (
          items.map((d, idx) => (
            <div key={idx} style={{ marginBottom: 8 }}>
              <div>
                <b>{d.severity}</b> line {d.line}: {d.message}
              </div>
              {d.text ? <div style={{ opacity: 0.8, fontFamily: "monospace" }}>{d.text}</div> : null}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export function StatusPillLarge({ status, hint }) {
  const s = status === "WARN" ? "warn" : status === "BLOCKED" ? "blocked" : "safe";
  const bg = s === "safe" ? "#022c22" : s === "warn" ? "#422c02" : "#3b0a0a";
  const border = s === "safe" ? "#16a34a" : s === "warn" ? "#eab308" : "#f97373";
  const color = s === "safe" ? "#bbf7d0" : s === "warn" ? "#fef08a" : "#fecaca";
  const label = s === "safe" ? "✅ SAFE" : s === "warn" ? "⚠ WARN" : "⛔ BLOCKED";
  const guidance =
    hint != null && String(hint).trim() !== ""
      ? hint
      : s === "safe"
        ? "Hazır. Çizime geçebilirsiniz."
        : s === "warn"
          ? "Çizilebilir ama uyarılar var. İstersen çizime geç, istersen Plan'da ayarları değiştir."
          : "Bu ayarlarla güvenli değil. Aşağıdan bir seçenek seçin.";
  return (
    <div style={{ textAlign: "center" }}>
      <div style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", padding: "8px 18px", borderRadius: 999, border: `1px solid ${border}`, background: bg, color, fontWeight: 800, fontSize: 16, letterSpacing: 0.4 }}>
        {label}
      </div>
      <div style={{ marginTop: 8, fontSize: 13, opacity: 0.9 }}>{guidance}</div>
    </div>
  );
}
