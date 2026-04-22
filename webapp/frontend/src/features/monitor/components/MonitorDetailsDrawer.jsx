import React from "react";
import { DiagList } from "../../../components/SimulationUiBits.jsx";

function Section({ title, children, defaultOpen = false }) {
  return (
    <details className="mon2-details__section" open={defaultOpen}>
      <summary className="mon2-details__summary">{title}</summary>
      <div className="mon2-details__content">{children}</div>
    </details>
  );
}

export default function MonitorDetailsDrawer({
  open,
  onToggle,
  bundle,
  lastRun,
  ctx,
  blocked,
  streamError,
  eventLogTail,
  lastTick,
  lastEvent,
}) {
  return (
    <section className="mon2-details" aria-label="Detaylar">
      <button type="button" className="mon2-btn mon2-btn--ghost" onClick={onToggle}>
        {open ? "Detayları kapat" : "Detayları aç"}
      </button>

      {open ? (
        <div className="mon2-details__panel">
          <Section title="Olay akışı (son satırlar)" defaultOpen={false}>
            <div className="mon2-log" role="log">
              {(eventLogTail ?? []).length === 0 ? (
                <div className="mon2-muted mon2-muted--sm">(Olay yok)</div>
              ) : (
                (eventLogTail ?? []).map((row) => (
                  <div key={row.id} className="mon2-log__line">
                    <span className="mon2-log__ev">{row.eventName}</span>
                    <span className="mon2-log__detail">{row.detail}</span>
                  </div>
                ))
              )}
            </div>
          </Section>

          <Section title="Son tick (ham)" defaultOpen={false}>
            <pre className="mon2-pre">{lastTick ? JSON.stringify(lastTick, null, 2) : "(tick yok)"}</pre>
          </Section>

          <Section title="Son olay (ham)" defaultOpen={false}>
            <pre className="mon2-pre">{lastEvent ? JSON.stringify(lastEvent, null, 2) : "(olay yok)"}</pre>
          </Section>

          <Section title="Engellendi (diag)" defaultOpen={Boolean(blocked)}>
            {blocked ? (
              <>
                <DiagList title="Parser" items={blocked.parser_diags || []} />
                <DiagList title="Analysis" items={blocked.analysis_diags || []} />
              </>
            ) : (
              <div className="mon2-muted mon2-muted--sm">(yok)</div>
            )}
          </Section>

          <Section title="Akış hatası" defaultOpen={Boolean(streamError)}>
            {streamError ? <div className="mon2-inline-error">{streamError}</div> : <div className="mon2-muted mon2-muted--sm">(yok)</div>}
          </Section>

          <Section title="Ham: monitor bundle" defaultOpen={false}>
            <pre className="mon2-pre">{bundle ? JSON.stringify(bundle, null, 2) : "(bundle yok)"}</pre>
          </Section>

          <Section title="Ham: last run" defaultOpen={false}>
            <pre className="mon2-pre">{lastRun ? JSON.stringify(lastRun, null, 2) : "(kayıt yok)"}</pre>
          </Section>

          <Section title="Ham: execution snapshot" defaultOpen={false}>
            <pre className="mon2-pre">{ctx ? JSON.stringify(ctx, null, 2) : "(anlık yok)"}</pre>
          </Section>
        </div>
      ) : null}
    </section>
  );
}

