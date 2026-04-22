import React from "react";
import { Link } from "react-router-dom";

function fmtNum(x, digits = 4) {
  if (x == null) return "—";
  const n = Number(x);
  if (!Number.isFinite(n)) return String(x);
  return n.toFixed(digits);
}

function Gate({ tone, title, lead, children }) {
  const cls =
    tone === "ok"
      ? "align2-gate align2-gate--ok"
      : tone === "warn"
        ? "align2-gate align2-gate--warn"
        : tone === "err"
          ? "align2-gate align2-gate--err"
          : "align2-gate align2-gate--idle";
  return (
    <div className={cls}>
      <div className="align2-gate__title">{title}</div>
      <div className="align2-gate__lead">{lead}</div>
      {children}
    </div>
  );
}

export default function AlignReadinessCard({ phase, lastAlignment, toleranceM, filledRowCount, onOpenDetails }) {
  const blocked = Boolean(lastAlignment?.blocked);
  const hasResult = Boolean(lastAlignment);
  const allowed = hasResult && !blocked;

  const gate = (() => {
    if (phase === "no_pipeline") {
      return {
        tone: "warn",
        title: "Eksik veri",
        lead: "Hizalama için önce Prepare/Plan üzerinden duvar ve komut bağlamı oluşturun.",
      };
    }
    if (phase === "cp_missing") {
      return {
        tone: "warn",
        title: "Kontrol noktası eksik",
        lead: "En az iki tam satır kontrol noktası girin (cad_x, cad_y, site_x, site_y).",
      };
    }
    if (phase === "not_run") {
      return {
        tone: "idle",
        title: "Hizalama yapılmadı",
        lead: "Kontrol noktalarını girip “Hizalamayı çalıştır” ile doğrulayın.",
      };
    }
    if (phase === "blocked") {
      return {
        tone: "err",
        title: "Engelli",
        lead: "Residual tolerans dışı veya geometri tekilliği var. Noktaları düzeltin veya toleransı ayarlayın.",
      };
    }
    if (phase === "allowed") {
      return {
        tone: "ok",
        title: "İzin verildi",
        lead: "Hizalama uygun. Bir sonraki adım için Plan’a geçebilirsiniz.",
      };
    }
    return { tone: "idle", title: "Bekliyor", lead: "Durum güncelleniyor." };
  })();

  return (
    <section className="align2-card" aria-label="Hazırlık ve karar">
      <div className="align2-card__head">
        <h2 className="align2-card__h">Karar</h2>
        <p className="align2-muted">Bu panel “devam edebilir miyim?” sorusunu yanıtlar. Teknik detaylar Detaylar’dadır.</p>
      </div>
      <div className="align2-card__body">
        <Gate tone={gate.tone} title={gate.title} lead={gate.lead}>
          <div className="align2-gate__meta">
            <div className="align2-kv">
              <span className="align2-kv__k">Nokta</span>
              <span className="align2-kv__v">{filledRowCount}</span>
            </div>
            <div className="align2-kv">
              <span className="align2-kv__k">Tolerans (m)</span>
              <span className="align2-kv__v">{fmtNum(toleranceM, 3)}</span>
            </div>
            {hasResult ? (
              <>
                <div className="align2-kv">
                  <span className="align2-kv__k">Residual ort</span>
                  <span className="align2-kv__v">{fmtNum(lastAlignment?.residual_mean_m, 4)}</span>
                </div>
                <div className="align2-kv">
                  <span className="align2-kv__k">Residual max</span>
                  <span className="align2-kv__v">{fmtNum(lastAlignment?.residual_max_m, 4)}</span>
                </div>
              </>
            ) : null}
          </div>
          <div className="align2-gate__actions">
            <button type="button" className="align2-btn align2-btn--ghost" onClick={onOpenDetails}>
              Detayları aç
            </button>
          </div>
        </Gate>

        <div className="align2-next">
          <div className="align2-next__label">Sıradaki adım</div>
          {allowed ? (
            <Link to="/plan" className="align2-btn align2-btn--primary">
              Plan’a geç
            </Link>
          ) : blocked ? (
            <div className="align2-muted align2-muted--sm">Öneri: noktaları düzeltin veya toleransı artırıp tekrar deneyin.</div>
          ) : (
            <div className="align2-muted align2-muted--sm">Hizalama uygun olunca Plan’a geçiş burada aktif olur.</div>
          )}
        </div>
      </div>
    </section>
  );
}

