/**
 * StepperNav — 3 adım: Plan → Çizim → Analiz
 */
import React from "react";

export default function StepperNav({ step, onGoToStep, canGoToCizim, canGoToAnaliz }) {
  const steps = [
    { id: "plan", label: "1 Plan" },
    { id: "draw", label: "2 Çizim" },
    { id: "analyze", label: "3 Analiz" },
  ];
  const stepOrder = ["plan", "draw", "analyze"];
  const currentIndex = stepOrder.indexOf(step);

  return (
    <nav
      style={{
        display: "flex",
        alignItems: "center",
        gap: 4,
        marginTop: 12,
        marginBottom: 16,
        padding: "10px 14px",
        background: "#151515",
        borderRadius: 12,
        border: "1px solid #333",
      }}
    >
      {steps.map((s, idx) => {
        const isActive = step === s.id;
        const isPast = currentIndex > idx;
        const canGo =
          idx === 0 ||
          (idx === 1 && canGoToCizim) ||
          (idx === 2 && canGoToAnaliz);
        return (
          <React.Fragment key={s.id}>
            <button
              type="button"
              onClick={() => canGo && onGoToStep(s.id)}
              disabled={!canGo}
              style={{
                padding: "8px 16px",
                borderRadius: 8,
                border: "1px solid #444",
                background: isActive ? "#1d3b7a" : isPast ? "#1e3a1e" : "#222",
                color: canGo ? "#fff" : "#666",
                cursor: canGo ? "pointer" : "default",
                fontWeight: 600,
                fontSize: 13,
              }}
            >
              {s.label}
            </button>
            {idx < steps.length - 1 && (
              <span style={{ color: "#444", fontSize: 12 }}>→</span>
            )}
          </React.Fragment>
        );
      })}
    </nav>
  );
}
