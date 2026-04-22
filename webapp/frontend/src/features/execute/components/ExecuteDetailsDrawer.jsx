import React from "react";
import { DiagList } from "../../../components/SimulationUiBits.jsx";

function Section({ title, children, defaultOpen = false }) {
  return (
    <details className="exec2-details__section" open={defaultOpen}>
      <summary className="exec2-details__summary">{title}</summary>
      <div className="exec2-details__content">{children}</div>
    </details>
  );
}

export default function ExecuteDetailsDrawer({
  open,
  onToggle,
  // simulation details
  blockedSim,
  tickState,
  donePayload,
  streamError,
  eventLog,
  // robot details
  serialResult,
}) {
  return (
    <section className="exec2-details" aria-label="Detaylar">
      <button type="button" className="exec2-btn exec2-btn--ghost" onClick={onToggle}>
        {open ? "Detayları kapat" : "Detayları aç"}
      </button>

      {open ? (
        <div className="exec2-details__panel">
          <Section title="Son tick (ham)" defaultOpen={false}>
            <pre className="exec2-pre">{tickState ? JSON.stringify(tickState, null, 2) : "(tick yok)"}</pre>
          </Section>

          <Section title="Done payload (ham)" defaultOpen={false}>
            <pre className="exec2-pre">{donePayload ? JSON.stringify(donePayload, null, 2) : "(done yok)"}</pre>
          </Section>

          <Section title="Event log (ham)" defaultOpen={false}>
            <pre className="exec2-pre">{Array.isArray(eventLog) ? JSON.stringify(eventLog.slice(-200), null, 2) : "[]"}</pre>
          </Section>

          <Section title="Job blocked (diag)" defaultOpen={Boolean(blockedSim)}>
            {blockedSim ? (
              <>
                <DiagList title="Parser" items={blockedSim.parser_diags || []} />
                <DiagList title="Analysis" items={blockedSim.analysis_diags || []} />
              </>
            ) : (
              <div className="exec2-muted exec2-muted--sm">(blocked yok)</div>
            )}
          </Section>

          <Section title="Akış hatası" defaultOpen={Boolean(streamError)}>
            {streamError ? <div className="exec2-inline-error">{streamError}</div> : <div className="exec2-muted exec2-muted--sm">(yok)</div>}
          </Section>

          <Section title="Seri sonuç (ham)" defaultOpen={Boolean(serialResult)}>
            <pre className="exec2-pre">{serialResult ? JSON.stringify(serialResult, null, 2) : "(seri sonucu yok)"}</pre>
          </Section>
        </div>
      ) : null}
    </section>
  );
}

