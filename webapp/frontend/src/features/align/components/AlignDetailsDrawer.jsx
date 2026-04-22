import React from "react";
import AlignmentSummaryCard from "./AlignmentSummaryCard.jsx";

function Section({ title, children, defaultOpen = false }) {
  return (
    <details className="align2-details__section" open={defaultOpen}>
      <summary className="align2-details__summary">{title}</summary>
      <div className="align2-details__content">{children}</div>
    </details>
  );
}

export default function AlignDetailsDrawer({
  open,
  onToggle,
  jsonText,
  setJsonText,
  applyJson,
  exportJson,
  lastAlignment,
  error,
}) {
  return (
    <section className="align2-details" aria-label="Detaylar">
      <button type="button" className="align2-btn align2-btn--ghost" onClick={onToggle}>
        {open ? "Detayları kapat" : "Detayları aç"}
      </button>

      {open ? (
        <div className="align2-details__panel">
          <Section title="JSON (isteğe bağlı)" defaultOpen={false}>
            <p className="align2-muted align2-muted--sm">
              Biçim: <code className="align2-code">{`{ "tolerance_m": 0.05, "points": [...] }`}</code>
            </p>
            <textarea
              className="align2-textarea"
              rows={4}
              value={jsonText}
              onChange={(e) => setJsonText(e.target.value)}
              placeholder='{"tolerance_m": 0.05, "points": [...]}'
            />
            <div className="align2-row">
              <button type="button" className="align2-btn" onClick={applyJson}>
                JSON uygula
              </button>
              <button
                type="button"
                className="align2-btn align2-btn--ghost"
                onClick={() => {
                  navigator.clipboard?.writeText(exportJson());
                }}
              >
                Panoya kopyala
              </button>
            </div>
          </Section>

          <Section title="Hizalama özeti (detay)" defaultOpen={Boolean(lastAlignment)}>
            <AlignmentSummaryCard alignment={lastAlignment} />
          </Section>

          {error ? (
            <Section title="Hata" defaultOpen={true}>
              <div className="align2-inline-error">{error}</div>
            </Section>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

