import React from "react";
import { Link } from "react-router-dom";

function Gate({ tone, title, lead, children }) {
  const cls =
    tone === "ok"
      ? "exec2-gate exec2-gate--ok"
      : tone === "warn"
        ? "exec2-gate exec2-gate--warn"
        : tone === "err"
          ? "exec2-gate exec2-gate--err"
          : "exec2-gate exec2-gate--idle";
  return (
    <div className={cls}>
      <div className="exec2-gate__title">{title}</div>
      <div className="exec2-gate__lead">{lead}</div>
      {children}
    </div>
  );
}

export default function ExecuteReadinessCard({
  mode,
  commandReady,
  alignGate,
  simRunning,
  footerPhase,
  donePayload,
  serialResult,
  serialError,
  onOpenDetails,
}) {
  const simGate = (() => {
    if (!commandReady) return { tone: "warn", title: "Eksik veri", lead: "Komut metni yok. Önce Prepare/Plan üzerinden komut üretin." };
    if (footerPhase === "blocked") return { tone: "err", title: "Engellendi", lead: "Job oluşturulamadı (parser/analysis). Detaylara bakın." };
    if (footerPhase === "error") return { tone: "err", title: "Hata", lead: "Akış hatası var. Detayları açıp hata mesajını kontrol edin." };
    if (footerPhase === "running") return { tone: "idle", title: "Çalışıyor", lead: "Simülasyon job akışı devam ediyor." };
    if (footerPhase === "done") return { tone: "ok", title: "Tamamlandı", lead: "Simülasyon tamamlandı. Robot adımına geçebilirsiniz." };
    return { tone: "idle", title: "Hazır", lead: "Simülasyonu başlatabilirsiniz." };
  })();

  const robotGate = (() => {
    if (!commandReady) return { tone: "warn", title: "Eksik veri", lead: "Komut metni yok. Önce Prepare/Plan üzerinden komut üretin." };
    if (alignGate === "blocked") return { tone: "warn", title: "Hizalama engelli", lead: "Hizalama kapısı kapalı. Yine de ön kontrol yapabilirsiniz; canlı gönderim önerilmez." };
    if (serialError) return { tone: "err", title: "Seri hata", lead: "Seri yürütme başarısız. Mesajı ve hata kodunu kontrol edin." };
    if (serialResult && serialResult.status) {
      const st = String(serialResult.status);
      if (st === "dry_run") return { tone: "ok", title: "Ön kontrol tamam", lead: "Artifact üretildi. Canlı gönderim için onay vererek devam edin." };
      if (st === "sent") return { tone: "ok", title: "Gönderildi", lead: "Komutlar robota gönderildi. Monitor ile izleyebilirsiniz." };
      if (st === "failed") return { tone: "err", title: "Seri başarısız", lead: "Sürücü/port/firmware hatası olabilir. Detaylara bakın." };
    }
    return { tone: "idle", title: "Hazır", lead: "Önerilen sıra: önce seri ön kontrol, sonra kontrollü canlı gönderim." };
  })();

  const gate = mode === "robot" ? robotGate : simGate;
  const nextLabel = mode === "robot" ? "Sıradaki adım" : "Sıradaki adım";

  return (
    <section className="exec2-card" aria-label="Karar">
      <div className="exec2-card__head">
        <h2 className="exec2-card__h">Karar</h2>
        <p className="exec2-muted">Bu panel “şimdi ne yapmalıyım?” sorusuna tek cevap verir. Teknik detaylar Detaylar’da.</p>
      </div>
      <div className="exec2-card__body">
        <Gate tone={gate.tone} title={gate.title} lead={gate.lead}>
          <div className="exec2-gate__actions">
            <button type="button" className="exec2-btn exec2-btn--ghost" onClick={onOpenDetails} disabled={simRunning}>
              Detayları aç
            </button>
          </div>
          {mode === "robot" && serialError ? <div className="exec2-inline-error">{serialError}</div> : null}
        </Gate>

        <div className="exec2-next">
          <div className="exec2-next__label">{nextLabel}</div>
          {mode === "simulate" ? (
            <div className="exec2-muted exec2-muted--sm">
              Simülasyon tamamlanınca Robot moduna geçip önce ön kontrol yapın.
            </div>
          ) : (
            <div className="exec2-next__row">
              <Link to="/monitor" className="exec2-btn exec2-btn--ghost">
                Monitor’a geç
              </Link>
              <span className="exec2-muted exec2-muted--sm">
                Canlı gönderim yaptıysanız veya job çalıştırdıysanız son durumu burada izleyin.
              </span>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

