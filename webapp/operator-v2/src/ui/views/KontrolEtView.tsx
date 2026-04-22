import React, { useMemo } from "react";
import { useMutation } from "@tanstack/react-query";
import { COPY } from "../../content";
import { analyzeCommands } from "../../data/services/operatorService";
import { PageLayout } from "../layout/PageLayout";
import { useWorkflowStore } from "../../workflow/store/workflowStore";

function formatValue(value?: number) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "—";
  }

  return value.toFixed(2);
}

export function KontrolEtView() {
  const planHazirligi = useWorkflowStore((state) => state.planHazirligi);
  const kontrolDurumu = useWorkflowStore((state) => state.kontrolDurumu);
  const setAktifAsama = useWorkflowStore((state) => state.setAktifAsama);
  const setHataMesaji = useWorkflowStore((state) => state.setHataMesaji);
  const setKontrolDurumu = useWorkflowStore((state) => state.setKontrolDurumu);

  React.useEffect(() => {
    setAktifAsama("kontrol-et");
  }, [setAktifAsama]);

  const hazir = Boolean(planHazirligi?.komutMetni.trim());

  const analizMutation = useMutation({
    mutationFn: async () => {
      if (!planHazirligi?.komutMetni.trim()) {
        throw new Error(COPY.ekranlar.kontrolEt.mesajlar.planHazirDegil);
      }

      return analyzeCommands(planHazirligi.komutMetni, planHazirligi.duvarlar);
    },
    onMutate: () => {
      setHataMesaji("");
    },
    onSuccess: (yanit) => {
      setKontrolDurumu({
        endpoint: "/api/analyze",
        mesaj: yanit.blocked
          ? COPY.ekranlar.kontrolEt.mesajlar.kontrolEngelli
          : COPY.ekranlar.kontrolEt.mesajlar.kontrolHazir,
        durum: yanit.blocked ? "dikkat" : "hazir",
        yanit,
        guncellenmeZamani: Date.now(),
      });
    },
    onError: (error) => {
      const mesaj = error instanceof Error ? error.message : COPY.geriBildirim.hata.genel;
      setHataMesaji(mesaj);
      setKontrolDurumu(null);
    },
  });

  const anaDurum = useMemo(() => {
    if (!hazir) {
      return {
        etiket: COPY.durumlar.engelli,
        mesaj: COPY.ekranlar.kontrolEt.mesajlar.planHazirDegil,
        ton: "dikkat",
      };
    }

    if (kontrolDurumu) {
      return {
        etiket:
          kontrolDurumu.durum === "hazir" ? COPY.durumlar.hazir : COPY.durumlar.dikkat,
        mesaj: kontrolDurumu.mesaj,
        ton: kontrolDurumu.durum,
      };
    }

    return {
      etiket: COPY.durumlar.bekliyor,
      mesaj: COPY.ekranlar.kontrolEt.mesajlar.kontrolBekliyor,
      ton: "bekliyor",
    };
  }, [hazir, kontrolDurumu]);

  const parserKayitlari = kontrolDurumu?.yanit.parser ?? [];
  const analizKayitlari = kontrolDurumu?.yanit.analysis ?? [];
  const stats = kontrolDurumu?.yanit.stats;

  const aside = (
    <>
      <section className={`panel stage-readiness stage-readiness--${anaDurum.ton}`}>
        <p className="panel__eyebrow">{COPY.ortak.hazirOlmaDurumu}</p>
        <strong className="panel__value">{anaDurum.etiket}</strong>
        <p className="panel__text">{anaDurum.mesaj}</p>
      </section>

      <section className="panel">
        <p className="panel__eyebrow">{COPY.ortak.sonrakiAdim}</p>
        <strong className="panel__value">
          {kontrolDurumu && !kontrolDurumu.yanit.blocked
            ? COPY.asamalar.calistir.baslik
            : COPY.asamalar.kontrolEt.baslik}
        </strong>
        <p className="panel__text">
          {kontrolDurumu && !kontrolDurumu.yanit.blocked
            ? COPY.ekranlar.kontrolEt.sonrakiAdimHazir
            : COPY.ekranlar.kontrolEt.sonrakiAdimBekliyor}
        </p>
      </section>
    </>
  );

  return (
    <PageLayout
      baslik={COPY.ekranlar.kontrolEt.ustBaslik}
      aciklama={COPY.ekranlar.kontrolEt.ustAciklama}
      aside={aside}
    >
      <section className="panel stage-primary">
        <p className="panel__eyebrow">{COPY.ekranlar.kontrolEt.anaPanelBasligi}</p>
        <h3 className="stage-title">{COPY.ekranlar.kontrolEt.ozetBaslik}</h3>
        <p className="panel__text">{COPY.ekranlar.kontrolEt.ozetAciklama}</p>

        <div className="stage-inline-meta stage-inline-meta--wide">
          <div>
            <span>{COPY.ortak.endpointBilgisi}</span>
            <strong>/api/analyze</strong>
          </div>
          <div>
            <span>{COPY.ekranlar.kontrolEt.komutDurumu}</span>
            <strong>{hazir ? COPY.durumlar.hazir : COPY.durumlar.engelli}</strong>
          </div>
          <div>
            <span>{COPY.ekranlar.kontrolEt.moveSayisi}</span>
            <strong>{stats?.move_count ?? "—"}</strong>
          </div>
          <div>
            <span>{COPY.ekranlar.kontrolEt.carpismaSayisi}</span>
            <strong>{stats?.collision_count ?? "—"}</strong>
          </div>
        </div>

        <div className="stage-footer">
          <p>{COPY.ekranlar.kontrolEt.tekAnaIs}</p>
          <button
            className="primary-button"
            type="button"
            onClick={() => analizMutation.mutate()}
            disabled={!hazir || analizMutation.isPending}
          >
            {analizMutation.isPending ? COPY.durumlar.calisiyor : COPY.butonlar.kontroluCalistir}
          </button>
        </div>
      </section>

      <section className="stage-summary-grid">
        <article className="panel">
          <p className="panel__eyebrow">{COPY.ekranlar.kontrolEt.kontrolSonucu}</p>
          <div className="stage-inline-meta stage-inline-meta--wide">
            <div>
              <span>{COPY.ekranlar.kontrolEt.tahminiSure}</span>
              <strong>{formatValue(stats?.estimated_time)}</strong>
            </div>
            <div>
              <span>{COPY.ekranlar.kontrolEt.yolUzunlugu}</span>
              <strong>{formatValue(stats?.path_length)}</strong>
            </div>
            <div>
              <span>{COPY.ekranlar.kontrolEt.azalmaOrani}</span>
              <strong>{formatValue(stats?.reduction_ratio)}</strong>
            </div>
            <div>
              <span>{COPY.ekranlar.kontrolEt.duvarTemasi}</span>
              <strong>{stats?.wall_touch_count ?? "—"}</strong>
            </div>
          </div>
        </article>

        <article className="panel">
          <p className="panel__eyebrow">{COPY.ekranlar.kontrolEt.bulguBaslik}</p>
          {parserKayitlari.length || analizKayitlari.length ? (
            <div className="diagnostic-list">
              {[...parserKayitlari, ...analizKayitlari].map((kayit, index) => (
                <div className="diagnostic-item" key={`${kayit.message}-${index}`}>
                  <strong>{kayit.severity}</strong>
                  <p>{kayit.message}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="panel__text">{COPY.ekranlar.kontrolEt.mesajlar.bulguYok}</p>
          )}
        </article>
      </section>

      <details className="panel">
        <summary className="details-summary">{COPY.ortak.teknikDetaylar}</summary>
        <div className="stage-inline-meta stage-inline-meta--wide">
          <div>
            <span>{COPY.ekranlar.kontrolEt.unrolledKomutlar}</span>
            <strong>{kontrolDurumu?.yanit.commands_unrolled ? COPY.durumlar.hazir : "Yok"}</strong>
          </div>
          <div>
            <span>{COPY.ekranlar.kontrolEt.pathNoktasi}</span>
            <strong>{stats?.path_points?.length ?? 0}</strong>
          </div>
        </div>
      </details>
    </PageLayout>
  );
}
