import React from "react";

export default function ExecuteModeSwitch({ mode, onChange, simRunning }) {
  return (
    <div className="exec2-mode" role="tablist" aria-label="Çalıştırma modu">
      <button
        type="button"
        className={"exec2-mode__tab" + (mode === "simulate" ? " exec2-mode__tab--active" : "")}
        onClick={() => onChange("simulate")}
        disabled={simRunning}
        role="tab"
        aria-selected={mode === "simulate"}
      >
        Simülasyon
      </button>
      <button
        type="button"
        className={"exec2-mode__tab" + (mode === "robot" ? " exec2-mode__tab--active" : "")}
        onClick={() => onChange("robot")}
        disabled={simRunning}
        role="tab"
        aria-selected={mode === "robot"}
      >
        Robot
      </button>
      {simRunning ? <span className="exec2-muted exec2-muted--sm">Job çalışırken mod değişmez.</span> : null}
    </div>
  );
}

