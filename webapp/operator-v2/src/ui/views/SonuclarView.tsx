import React, { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { COPY } from "../../content";
import { exportCommands } from "../../data/services/operatorService";
import { PageLayout } from "../layout/PageLayout";
import { useWorkflowStore } from "../../workflow/store/workflowStore";

type ExportFormat = "robot_v1" | "gcode_lite";

function formatValue(value?: number) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "—";
  }

  return value.toFixed(2);
}

export function SonuclarView() {
  const planHazirligi = useWorkflowStore((state) => state.planHazirligi);
  const hizalamaDurumu = useWorkflowStore((state) => state.hizalamaDurumu);
  const kontrolDurumu = useWorkflowStore((state) => state.kontrolDurumu);
  const calistirmaOzeti = useWorkflowStore((state) => state.calistirmaOzeti);
  const sonucCiktisi = useWorkflowStore((state) => state.sonucCiktisi);
  const setAktifAsama = useWorkflowStore((state) => state.setAktifAsama);
  const setSonucCiktisi = useWorkflowStore((state) => state.setSonucCiktisi);
  const setHataMesaji = useWorkflowStore((state) => state.setHataMesaji);

  const [format, setFormat] = useState<ExportFormat>(sonucCiktisi?.format ?? "robot_v1");

  React.useEffect(() => {
    setAktifAsama("sonuclar");
  }, [setAktifAsama]);

  const hazir = Boolean(planHazirligi?.komutMetni.trim());

  const exportMutation = useMutation({
    mutationFn: async () => {
      if (!planHazirligi?.komutMetni.trim()) {
        throw new Error(COPY.ekranlar.sonuclar.mesajlar.planHazirDegil);
      }

      return exportCommands(planHazirligi.komutMetni, { format });
    },
    onMutate: () => {
      setHataMesaji("");
    },
    onSuccess: (yanit) => {
      setSonucCiktisi({
        endpoint: "/api/export",
        format,
        mesaj: yanit.blocked
          ? COPY.ekranlar.sonuclar.mesajlar.ciktiUyarili
          : COPY.ekranlar.sonuclar.mesajlar.ciktiHazir,
        durum: yanit.blocked ? "dikkat" : "hazir",
        yanit,
        guncellenmeZamani: Date.now(),
      });
    },
    onError: (error) => {
      const mesaj = error instanceof Error ? error.message : COPY.geriBildirim.hata.genel;
      setHataMesaji(mesaj);
      setSonucCiktisi(null);
    },
  });

  const anaDurum = useMemo(() => {
    if (!hazir) {
      return {
        etiket: COPY.durumlar.engelli,
        mesaj: COPY.ekranlar.sonuclar.mesajlar.planHazirDegil,
        ton: "dikkat",
      };
    }

    if (sonucCiktisi) {
      return {
        etiket:
          sonucCiktisi.durum === "hazir" ? COPY.durumlar.hazir : COPY.durumlar.dikkat,
        mesaj: sonucCiktisi.mesaj,
        ton: sonucCiktisi.durum,
      };
    }

    return {
      etiket: COPY.durumlar.bekliyor,
      mesaj: COPY.ekranlar.sonuclar.mesajlar.ciktiBekliyor,
      ton: "bekliyor",
    };
  }, [hazir, sonucCiktisi]);

  const aside = (
    <>
      <section className={`panel stage-readiness stage-readiness--${anaDurum.ton}`}>
        <p className="panel__eyebrow">{COPY.ortak.hazirOlmaDurumu}</p>
        <strong className="panel__value">{anaDurum.etiket}</strong>
        <p className="panel__text">{anaDurum.mesaj}</p>
      </section>

      <section className="panel">
        <p className="panel__eyebrow">{COPY.ekranlar.sonuclar.okunanStateBasligi}</p>
        <div className="diagnostic-list">
          {[
            COPY.ekranlar.sonuclar.stateKalemi("Plan", Boolean(planHazirligi)),
            COPY.ekranlar.sonuclar.stateKalemi("Hizalama", Boolean(hizalamaDurumu)),
            COPY.ekranlar.sonuclar.stateKalemi("Kontrol", Boolean(kontrolDurumu)),
            COPY.ekranlar.sonuclar.stateKalemi("Çalıştır", Boolean(calistirmaOzeti)),
            COPY.ekranlar.sonuclar.stateKalemi("Çıktı", Boolean(sonucCiktisi)),
          ].map((satir) => (
            <div className="diagnostic-item" key={satir}>
              <p>{satir}</p>
            </div>
          ))}
        </div>
      </section>
    </>
  );

  return (
    <PageLayout
      baslik={COPY.ekranlar.sonuclar.ustBaslik}
      aciklama={COPY.ekranlar.sonuclar.ustAciklama}
      aside={aside}
    >
      <section className="panel stage-primary">
        <p className="panel__eyebrow">{COPY.ekranlar.sonuclar.anaPanelBasligi}</p>
        <h3 className="stage-title">{COPY.ekranlar.sonuclar.ciktiHazirlamaBasligi}</h3>
        <p className="panel__text">{COPY.ekranlar.sonuclar.ciktiHazirlamaAciklama}</p>

        <div className="stage-subcard">
          <p className="panel__eyebrow">{COPY.ekranlar.sonuclar.formatBasligi}</p>
          <div className="radio-row">
            <label className="radio-card">
              <input
                type="radio"
                checked={format === "robot_v1"}
                onChange={() => setFormat("robot_v1")}
              />
              <span>{COPY.ekranlar.sonuclar.robotFormat}</span>
            </label>
            <label className="radio-card">
              <input
                type="radio"
                checked={format === "gcode_lite"}
                onChange={() => setFormat("gcode_lite")}
              />
              <span>{COPY.ekranlar.sonuclar.gcodeFormat}</span>
            </label>
          </div>
        </div>

        <div className="stage-footer">
          <p>{COPY.ekranlar.sonuclar.tekAnaIs}</p>
          <button
            className="primary-button"
            type="button"
            onClick={() => exportMutation.mutate()}
            disabled={!hazir || exportMutation.isPending}
          >
            {exportMutation.isPending ? COPY.durumlar.calisiyor : COPY.butonlar.ciktiyiHazirla}
          </button>
        </div>
      </section>

      <section className="stage-summary-grid">
        <article className="panel">
          <p className="panel__eyebrow">{COPY.ekranlar.sonuclar.akisOzetiBaslik}</p>
          <div className="stage-inline-meta stage-inline-meta--wide">
            <div>
              <span>{COPY.ekranlar.sonuclar.planKaynagi}</span>
              <strong>{planHazirligi?.girdiAdi ?? "Yok"}</strong>
            </div>
            <div>
              <span>{COPY.ekranlar.sonuclar.hizalamaOzeti}</span>
              <strong>
                {hizalamaDurumu?.yanit.alignment
                  ? `${formatValue(hizalamaDurumu.yanit.alignment.residual_max_m)} m`
                  : "Bekleniyor"}
              </strong>
            </div>
            <div>
              <span>{COPY.ekranlar.sonuclar.kontrolOzeti}</span>
              <strong>
                {kontrolDurumu
                  ? kontrolDurumu.yanit.blocked
                    ? COPY.durumlar.dikkat
                    : COPY.durumlar.hazir
                  : "Bekleniyor"}
              </strong>
            </div>
            <div>
              <span>{COPY.ekranlar.sonuclar.calistirmaOzeti}</span>
              <strong>{calistirmaOzeti?.baslik ?? "Bekleniyor"}</strong>
            </div>
          </div>
        </article>

        <article className="panel">
          <p className="panel__eyebrow">{COPY.ekranlar.sonuclar.ciktiOzetiBaslik}</p>
          <div className="stage-inline-meta stage-inline-meta--wide">
            <div>
              <span>{COPY.ortak.endpointBilgisi}</span>
              <strong>/api/export</strong>
            </div>
            <div>
              <span>{COPY.ekranlar.sonuclar.dosyaAdi}</span>
              <strong>{sonucCiktisi?.yanit.filename ?? "Henüz yok"}</strong>
            </div>
            <div>
              <span>{COPY.ekranlar.sonuclar.ciktiDurumu}</span>
              <strong>{anaDurum.etiket}</strong>
            </div>
            <div>
              <span>{COPY.ekranlar.sonuclar.exportMoveSayisi}</span>
              <strong>{sonucCiktisi?.yanit.stats.move_count ?? "—"}</strong>
            </div>
          </div>
        </article>
      </section>

      <details className="panel">
        <summary className="details-summary">{COPY.ekranlar.sonuclar.icerikOnizlemeBaslik}</summary>
        {sonucCiktisi?.yanit.content ? (
          <pre className="output-preview">{sonucCiktisi.yanit.content}</pre>
        ) : (
          <p className="panel__text">{COPY.ekranlar.sonuclar.mesajlar.onizlemeYok}</p>
        )}
      </details>
    </PageLayout>
  );
}
