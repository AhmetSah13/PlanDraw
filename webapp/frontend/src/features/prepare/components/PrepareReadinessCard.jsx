import React from "react";
import { Link } from "react-router-dom";
import MetricsGrid from "../../../components/MetricsGrid.jsx";
import { StatusPillLarge } from "../../../components/SimulationUiBits.jsx";

function _analysisLevel(previewAnalyzeResult) {
  if (!previewAnalyzeResult) return "none";
  if (previewAnalyzeResult.blocked) return "blocked";
  const cc = Number(previewAnalyzeResult?.stats?.collision_count ?? 0);
  return cc > 0 ? "warning" : "ready";
}

function _humanStatus(level) {
  if (level === "ready") return { title: "Hazır", lead: "Komutlar üretildi ve doğrulama sonucu uygun.", tone: "ok" };
  if (level === "warning")
    return {
      title: "Dikkat",
      lead: "Komutlar üretildi; ancak doğrulamada risk işaretleri var. Detaylara bakıp gerekirse düzeltin.",
      tone: "warn",
    };
  if (level === "blocked")
    return {
      title: "Engellendi",
      lead: "Doğrulama blocked veya komut üretimi başarısız. Devam etmeden önce hatayı düzeltin.",
      tone: "err",
    };
  return {
    title: "Hazır değil",
    lead: "Önce planı içe aktarın veya manuel planı derleyin. Komut üretildikten sonra doğrulama çalıştırın.",
    tone: "idle",
  };
}

export default function PrepareReadinessCard({
  prepareReady,
  commandsReady,
  importBusy,
  compileBusy,
  compileError,
  lastImport,
  importWarningsCount,
  previewAnalyzeBusy,
  previewAnalyzeError,
  previewAnalyzeResult,
  onRunAnalyze,
  onOpenDetails,
}) {
  const analysisLevel = _analysisLevel(previewAnalyzeResult);
  const baseLevel = (() => {
    if (importBusy || compileBusy) return "none";
    if (compileError) return "blocked";
    if (lastImport && lastImport.ok === false) return "blocked";
    if (!commandsReady) return "none";
    if (!previewAnalyzeResult) return "warning";
    return analysisLevel;
  })();

  const human = _humanStatus(baseLevel === "none" ? "none" : baseLevel);
  const toneClass =
    human.tone === "ok"
      ? "prepare2-gate prepare2-gate--ok"
      : human.tone === "warn"
        ? "prepare2-gate prepare2-gate--warn"
        : human.tone === "err"
          ? "prepare2-gate prepare2-gate--err"
          : "prepare2-gate prepare2-gate--idle";

  const allowAlignPrimary = Boolean(prepareReady && previewAnalyzeResult && analysisLevel === "ready");
  const allowAlignSecondary = Boolean(prepareReady && (!previewAnalyzeResult || analysisLevel === "warning"));

  return (
    <section className="prepare2-card" aria-label="Hazırlık ve doğrulama">
      <div className="prepare2-card__head">
        <h2 className="prepare2-card__h">Hazırlık</h2>
        <p className="prepare2-muted">
          Bu panel “devam etmeye hazır mıyım?” sorusunu yanıtlar. Teknik ayrıntılar Detaylar bölümündedir.
        </p>
      </div>
      <div className="prepare2-card__body">
        <div className={toneClass}>
          <div className="prepare2-gate__title">{human.title}</div>
          <div className="prepare2-gate__lead">{human.lead}</div>
          {importWarningsCount > 0 ? (
            <div className="prepare2-gate__hint">
              İçe aktarma uyarısı: <strong>{importWarningsCount}</strong> (Detaylar’dan bakın)
            </div>
          ) : null}
          <div className="prepare2-gate__actions">
            <button
              type="button"
              className="prepare2-btn"
              onClick={onRunAnalyze}
              disabled={previewAnalyzeBusy || !commandsReady}
              title={!commandsReady ? "Önce komut üretin" : "Analiz çalıştır"}
            >
              {previewAnalyzeBusy ? "Doğrulanıyor…" : "Doğrulama (manuel)"}
            </button>
            <button type="button" className="prepare2-btn prepare2-btn--ghost" onClick={onOpenDetails}>
              Detayları aç
            </button>
          </div>
          {previewAnalyzeError ? <div className="prepare2-inline-error">{previewAnalyzeError}</div> : null}
        </div>

        {previewAnalyzeResult ? (
          <div className="prepare2-verify">
            <div className="prepare2-verify__row">
              <StatusPillLarge status={previewAnalyzeResult.blocked ? "BLOCKED" : analysisLevel === "warning" ? "WARN" : "SAFE"} />
              <div className="prepare2-verify__meta">
                <span className="prepare2-muted">
                  Çakışma: <strong>{Number(previewAnalyzeResult?.stats?.collision_count ?? 0)}</strong>
                </span>
              </div>
            </div>
            <MetricsGrid
              stats={previewAnalyzeResult?.stats}
              collisionCount={previewAnalyzeResult?.stats?.collision_count ?? 0}
              showDebugCounts={false}
            />
          </div>
        ) : null}

        <div className="prepare2-next">
          <div className="prepare2-next__label">Sıradaki adım</div>
          {allowAlignPrimary ? (
            <Link to="/align" className="prepare2-btn prepare2-btn--primary">
              Hizalamaya geç
            </Link>
          ) : allowAlignSecondary ? (
            <div className="prepare2-next__row">
              <Link to="/align" className="prepare2-btn prepare2-btn--ghost">
                Hizalamaya geç (dikkat)
              </Link>
              <span className="prepare2-muted prepare2-muted--sm">Öneri: önce doğrulama sonucunu SAFE yapın.</span>
            </div>
          ) : (
            <div className="prepare2-muted prepare2-muted--sm">
              Komut üretip doğrulama yaptıktan sonra “Hizalamaya geç” aktif olur.
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

