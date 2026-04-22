import React from "react";
import { Link } from "react-router-dom";
import MetricsGrid from "../../../components/MetricsGrid.jsx";
import { StatusPillLarge } from "../../../components/SimulationUiBits.jsx";

function Gate({ tone, title, lead, children }) {
  const cls =
    tone === "ok"
      ? "plan2-gate plan2-gate--ok"
      : tone === "warn"
        ? "plan2-gate plan2-gate--warn"
        : tone === "err"
          ? "plan2-gate plan2-gate--err"
          : "plan2-gate plan2-gate--idle";
  return (
    <div className={cls}>
      <div className="plan2-gate__title">{title}</div>
      <div className="plan2-gate__lead">{lead}</div>
      {children}
    </div>
  );
}

export default function PlanReadinessCard({
  executeReady,
  executeReadyStrict,
  commandsReady,
  analyzeBusy,
  analyzeError,
  analyzeResult,
  analysisStatus,
  blocked,
  collisionCount,
  onRunAnalyze,
  onOpenDetails,
}) {
  const gate = (() => {
    if (!commandsReady) {
      return { tone: "warn", title: "Eksik veri", lead: "Komut metni yok. Önce Prepare’den geçin veya planı yeniden derleyin." };
    }
    if (!analyzeResult) {
      return { tone: "warn", title: "Doğrulama yapılmadı", lead: "Execute’a geçmeden önce analizi çalıştırın (manuel)." };
    }
    if (blocked) {
      return { tone: "err", title: "Engelli", lead: "Analiz blocked. Önce hatayı düzeltmeden Execute’a geçmeyin." };
    }
    if (collisionCount > 0) {
      return { tone: "warn", title: "Dikkat", lead: "Çakışma tespit edildi. Operasyonel risk var; öneri: düzeltip tekrar analiz edin." };
    }
    return { tone: "ok", title: "Hazır", lead: "Analiz temiz. Execute’a güvenle geçebilirsiniz." };
  })();

  const allowExecutePrimary = Boolean(executeReadyStrict);
  const allowExecuteSecondary = Boolean(executeReady && !executeReadyStrict);

  return (
    <section className="plan2-card" aria-label="Karar ve doğrulama">
      <div className="plan2-card__head">
        <h2 className="plan2-card__h">Karar</h2>
        <p className="plan2-muted">Bu panel “Execute’a geçebilir miyim?” sorusunu yanıtlar. Teknik detaylar Detaylar’da.</p>
      </div>
      <div className="plan2-card__body">
        <Gate tone={gate.tone} title={gate.title} lead={gate.lead}>
          <div className="plan2-gate__actions">
            <button
              type="button"
              className="plan2-btn"
              onClick={onRunAnalyze}
              disabled={analyzeBusy || !commandsReady}
              title={!commandsReady ? "Önce komut üretin" : "Analiz çalıştır"}
            >
              {analyzeBusy ? "Analiz ediliyor…" : "Senaryoyu analiz et (manuel)"}
            </button>
            <button type="button" className="plan2-btn plan2-btn--ghost" onClick={onOpenDetails}>
              Detayları aç
            </button>
          </div>
          {analyzeError ? <div className="plan2-inline-error">{analyzeError}</div> : null}
        </Gate>

        {analyzeResult ? (
          <div className="plan2-verify">
            <div className="plan2-verify__row">
              <StatusPillLarge status={analysisStatus} />
              <div className="plan2-muted plan2-muted--sm">
                Çakışma: <strong>{collisionCount}</strong>
              </div>
            </div>
            <MetricsGrid stats={analyzeResult?.stats} collisionCount={collisionCount} showDebugCounts={false} />
          </div>
        ) : null}

        <div className="plan2-next">
          <div className="plan2-next__label">Sıradaki adım</div>
          {allowExecutePrimary ? (
            <Link to="/execute" className="plan2-btn plan2-btn--primary">
              Execute’a geç
            </Link>
          ) : allowExecuteSecondary ? (
            <div className="plan2-next__row">
              <Link to="/execute" className="plan2-btn plan2-btn--ghost">
                Execute’a geç (dikkat)
              </Link>
              <span className="plan2-muted plan2-muted--sm">Öneri: çakışmaları giderip SAFE duruma gelin.</span>
            </div>
          ) : (
            <div className="plan2-muted plan2-muted--sm">Analiz temiz olduğunda Execute’a geçiş burada aktif olur.</div>
          )}
        </div>
      </div>
    </section>
  );
}

