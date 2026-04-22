import React from "react";

export default function StageFrame({ title, lead, status, main, side }) {
  return (
    <section className="page">
      <header className="page-head">
        <div>
          <h1>{title}</h1>
          <p>{lead}</p>
        </div>
        <div className={`status-pill status-pill--${status || "idle"}`}>
          {status === "ready"
            ? "Hazır"
            : status === "warn" || status === "warning"
              ? "Dikkat"
              : status === "blocked"
                ? "Engelli"
                : status === "running"
                  ? "Calisiyor"
                  : status === "done"
                    ? "Tamamlandi"
                    : status === "error"
                      ? "Hata"
                      : "Bekliyor"}
        </div>
      </header>
      <div className="layout">
        <div className="stack">{main}</div>
        <aside className="stack">{side}</aside>
      </div>
    </section>
  );
}
