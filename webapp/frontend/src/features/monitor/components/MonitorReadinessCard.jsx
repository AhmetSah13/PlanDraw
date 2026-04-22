import React from "react";
import { Link } from "react-router-dom";
import { StatusPillLarge } from "../../../components/SimulationUiBits.jsx";

function Gate({ tone, title, lead, children }) {
  const cls =
    tone === "ok"
      ? "mon2-gate mon2-gate--ok"
      : tone === "warn"
        ? "mon2-gate mon2-gate--warn"
        : tone === "err"
          ? "mon2-gate mon2-gate--err"
          : "mon2-gate mon2-gate--idle";
  return (
    <div className={cls}>
      <div className="mon2-gate__title">{title}</div>
      <div className="mon2-gate__lead">{lead}</div>
      {children}
    </div>
  );
}

export default function MonitorReadinessCard({
  phase,
  phaseLabelTr,
  pillStatus,
  pillHint,
  lastUpdate,
  lastRun,
  alignGate,
  onOpenDetails,
}) {
  const gate = (() => {
    if (phase === "running")
      return {
        tone: "idle",
        title: "Canlı izleme",
        lead: "Job çalışıyor olabilir. Müdahale (durdur/yeniden başlat) için Execute ekranına dönün.",
      };
    if (phase === "done_ok")
      return {
        tone: "ok",
        title: "Tamamlandı",
        lead: "Son çalıştırma tamamlandı. Yeni çalıştırma veya farklı parametre için Execute’a dönebilirsiniz.",
      };
    if (phase === "blocked")
      return {
        tone: "err",
        title: "Engellendi",
        lead: "Job oluşturulamadı. Genelde komut/analiz engeli olur. Detaylara bakıp Plan/Execute tarafında düzeltin.",
      };
    if (phase === "failed" || phase === "stream_error")
      return {
        tone: "err",
        title: "Sorun var",
        lead: "Son çalıştırma hata verdi veya akış koptu. Detayları açıp hata mesajını kontrol edin.",
      };
    return {
      tone: "warn",
      title: "Beklemede",
      lead: "Henüz çalıştırma kaydı yok veya sadece anlık veri var. Job çalıştırmak için Execute’a gidin.",
    };
  })();

  const alignHint =
    alignGate === "allowed"
      ? "Hizalama uygun."
      : alignGate === "blocked"
        ? "Hizalama engelli: saha eşlemesini gözden geçirin."
        : "Hizalama yok: Align önerilir.";

  return (
    <section className="mon2-card" aria-label="Karar">
      <div className="mon2-card__head">
        <h2 className="mon2-card__h">Karar</h2>
        <p className="mon2-muted">Bu panel “ne oldu ve şimdi ne yapmalıyım?” sorusuna tek cevap verir.</p>
      </div>
      <div className="mon2-card__body">
        <div className="mon2-status">
          <div className="mon2-status__label">Son durum</div>
          <div className="mon2-status__pill">
            {phase === "running" ? (
              <div className="mon2-pill-run">ÇALIŞIYOR</div>
            ) : (
              <StatusPillLarge status={pillStatus} hint={pillHint} />
            )}
          </div>
          <div className="mon2-muted mon2-muted--sm">
            Aşama: <strong>{phaseLabelTr}</strong> · Son güncelleme: <strong>{lastUpdate || "—"}</strong>
          </div>
        </div>

        <Gate tone={gate.tone} title={gate.title} lead={gate.lead}>
          <div className="mon2-gate__actions">
            <button type="button" className="mon2-btn mon2-btn--ghost" onClick={onOpenDetails}>
              Detayları aç
            </button>
            <Link to="/execute" className="mon2-btn mon2-btn--primary">
              Execute’a dön
            </Link>
          </div>
          <div className="mon2-muted mon2-muted--sm" style={{ marginTop: 10 }}>
            Hizalama: {alignHint}
          </div>
        </Gate>

        {lastRun?.ok === false ? (
          <div className="mon2-inline-error" style={{ marginTop: 12 }}>
            Son hata: {lastRun.error || "Bilinmeyen hata"}
          </div>
        ) : null}

        <div className="mon2-next">
          <div className="mon2-next__label">Sıradaki adım</div>
          <div className="mon2-next__row">
            <Link to="/plan" className="mon2-btn mon2-btn--ghost">
              Plan’a dön
            </Link>
            <span className="mon2-muted mon2-muted--sm">Komut/parametre değişikliği veya doğrulama için.</span>
          </div>
        </div>
      </div>
    </section>
  );
}

