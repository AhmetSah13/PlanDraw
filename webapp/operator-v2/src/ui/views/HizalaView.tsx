import React, { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { COPY } from "../../content";
import { alignRigidLayout } from "../../data/services/operatorService";
import { PageLayout } from "../layout/PageLayout";
import {
  useWorkflowStore,
  type HizalamaKontrolNoktasi,
} from "../../workflow/store/workflowStore";
import { AlignmentOverlay } from "../components/AlignmentOverlay";
import { PlanCanvas } from "../components/PlanCanvas";

const DEFAULT_KONTROL_NOKTALARI: HizalamaKontrolNoktasi[] = [
  { cad_x: 0, cad_y: 0, site_x: 0, site_y: 0, label: "Nokta 1" },
  { cad_x: 10, cad_y: 0, site_x: 10, site_y: 0, label: "Nokta 2" },
  { cad_x: 0, cad_y: 10, site_x: 0, site_y: 10, label: "Nokta 3" },
];

function formatNumber(value?: number) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "—";
  }

  return value.toFixed(3);
}

export function HizalaView() {
  const planHazirligi = useWorkflowStore((state) => state.planHazirligi);
  const hizalamaDurumu = useWorkflowStore((state) => state.hizalamaDurumu);
  const setAktifAsama = useWorkflowStore((state) => state.setAktifAsama);
  const setHataMesaji = useWorkflowStore((state) => state.setHataMesaji);
  const setHizalamaDurumu = useWorkflowStore((state) => state.setHizalamaDurumu);

  const [toleranceM, setToleranceM] = useState("0.05");
  const [kontrolNoktalari, setKontrolNoktalari] = useState<HizalamaKontrolNoktasi[]>(
    hizalamaDurumu?.kontrolNoktalari ?? DEFAULT_KONTROL_NOKTALARI,
  );

  React.useEffect(() => {
    setAktifAsama("hizala");
  }, [setAktifAsama]);

  const hazir = Boolean(planHazirligi?.duvarlar.length);

  const anaDurum = useMemo(() => {
    if (!hazir) {
      return {
        etiket: COPY.durumlar.engelli,
        mesaj: COPY.ekranlar.hizala.mesajlar.planHazirDegil,
        ton: "dikkat",
      };
    }

    if (hizalamaDurumu) {
      return {
        etiket:
          hizalamaDurumu.durum === "hazir"
            ? COPY.durumlar.hazir
            : hizalamaDurumu.durum === "dikkat"
              ? COPY.durumlar.dikkat
              : COPY.durumlar.hata,
        mesaj: hizalamaDurumu.mesaj,
        ton: hizalamaDurumu.durum,
      };
    }

    return {
      etiket: COPY.durumlar.bekliyor,
      mesaj: COPY.ekranlar.hizala.mesajlar.bekleyenHizalama,
      ton: "bekliyor",
    };
  }, [hazir, hizalamaDurumu]);

  const hizalamaMutation = useMutation({
    mutationFn: async () => {
      if (!planHazirligi?.duvarlar.length) {
        throw new Error(COPY.ekranlar.hizala.mesajlar.planHazirDegil);
      }

      const tolerance = Number.parseFloat(toleranceM);
      if (!Number.isFinite(tolerance) || tolerance <= 0) {
        throw new Error(COPY.ekranlar.hizala.mesajlar.toleransGecersiz);
      }

      return alignRigidLayout({
        walls: planHazirligi.duvarlar,
        control_points: kontrolNoktalari.map((nokta) => ({
          cad_x: Number(nokta.cad_x),
          cad_y: Number(nokta.cad_y),
          site_x: Number(nokta.site_x),
          site_y: Number(nokta.site_y),
          label: nokta.label,
          weight: nokta.weight,
        })),
        tolerance_m: tolerance,
      });
    },
    onMutate: () => {
      setHataMesaji("");
    },
    onSuccess: (yanit) => {
      if (!yanit.ok || !yanit.alignment) {
        const mesaj = yanit.error ?? COPY.geriBildirim.hata.genel;
        setHataMesaji(mesaj);
        setHizalamaDurumu(null);
        return;
      }

      const blocked = Boolean(yanit.alignment.blocked);
      setHizalamaDurumu({
        endpoint: "/api/alignment/rigid_2d",
        toleranceM: Number.parseFloat(toleranceM),
        kontrolNoktalari,
        mesaj: blocked
          ? COPY.ekranlar.hizala.mesajlar.hizalamaRiskli
          : COPY.ekranlar.hizala.mesajlar.hizalamaHazir,
        durum: blocked ? "dikkat" : "hazir",
        yanit,
        guncellenmeZamani: Date.now(),
      });
    },
    onError: (error) => {
      const mesaj = error instanceof Error ? error.message : COPY.geriBildirim.hata.genel;
      setHataMesaji(mesaj);
      setHizalamaDurumu(null);
    },
  });

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
          {hizalamaDurumu ? COPY.asamalar.kontrolEt.baslik : COPY.asamalar.hizala.baslik}
        </strong>
        <p className="panel__text">
          {hizalamaDurumu
            ? COPY.ekranlar.hizala.sonrakiAdimHazir
            : COPY.ekranlar.hizala.sonrakiAdimBekliyor}
        </p>
      </section>
    </>
  );

  return (
    <PageLayout
      baslik={COPY.ekranlar.hizala.ustBaslik}
      aciklama={COPY.ekranlar.hizala.ustAciklama}
      aside={aside}
    >
      <section className="panel stage-primary">
        <p className="panel__eyebrow">{COPY.ekranlar.hizala.anaPanelBasligi}</p>
        <h3 className="stage-title">{COPY.ekranlar.hizala.kontrolNoktalariBasligi}</h3>
        <p className="panel__text">{COPY.ekranlar.hizala.kontrolNoktalariAciklama}</p>

        <div className="stage-inline-meta">
          <div>
            <span>{COPY.ortak.endpointBilgisi}</span>
            <strong>/api/alignment/rigid_2d</strong>
          </div>
          <div>
            <span>{COPY.ekranlar.hizala.duvarSayisi}</span>
            <strong>{planHazirligi?.duvarlar.length ?? 0}</strong>
          </div>
        </div>

        <label className="field">
          <span className="field__label">{COPY.ekranlar.hizala.toleransEtiketi}</span>
          <input
            className="field__control stage-input"
            type="number"
            step="0.01"
            min="0.01"
            value={toleranceM}
            onChange={(event) => setToleranceM(event.target.value)}
          />
        </label>

        <div className="stage-form-grid">
          {kontrolNoktalari.map((nokta, index) => (
            <div className="stage-subcard" key={`${nokta.label}-${index}`}>
              <label className="field">
                <span className="field__label">{COPY.ekranlar.hizala.noktaEtiketi(index + 1)}</span>
                <input
                  className="field__control stage-input"
                  type="text"
                  value={nokta.label}
                  onChange={(event) =>
                    setKontrolNoktalari((onceki) =>
                      onceki.map((satir, satirIndex) =>
                        satirIndex === index ? { ...satir, label: event.target.value } : satir,
                      ),
                    )
                  }
                />
              </label>
              <div className="stage-mini-grid">
                <label className="field">
                  <span className="field__label">{COPY.ekranlar.hizala.cadX}</span>
                  <input
                    className="field__control stage-input"
                    type="number"
                    value={nokta.cad_x}
                    onChange={(event) =>
                      setKontrolNoktalari((onceki) =>
                        onceki.map((satir, satirIndex) =>
                          satirIndex === index
                            ? { ...satir, cad_x: Number(event.target.value) }
                            : satir,
                        ),
                      )
                    }
                  />
                </label>
                <label className="field">
                  <span className="field__label">{COPY.ekranlar.hizala.cadY}</span>
                  <input
                    className="field__control stage-input"
                    type="number"
                    value={nokta.cad_y}
                    onChange={(event) =>
                      setKontrolNoktalari((onceki) =>
                        onceki.map((satir, satirIndex) =>
                          satirIndex === index
                            ? { ...satir, cad_y: Number(event.target.value) }
                            : satir,
                        ),
                      )
                    }
                  />
                </label>
                <label className="field">
                  <span className="field__label">{COPY.ekranlar.hizala.sahaX}</span>
                  <input
                    className="field__control stage-input"
                    type="number"
                    value={nokta.site_x}
                    onChange={(event) =>
                      setKontrolNoktalari((onceki) =>
                        onceki.map((satir, satirIndex) =>
                          satirIndex === index
                            ? { ...satir, site_x: Number(event.target.value) }
                            : satir,
                        ),
                      )
                    }
                  />
                </label>
                <label className="field">
                  <span className="field__label">{COPY.ekranlar.hizala.sahaY}</span>
                  <input
                    className="field__control stage-input"
                    type="number"
                    value={nokta.site_y}
                    onChange={(event) =>
                      setKontrolNoktalari((onceki) =>
                        onceki.map((satir, satirIndex) =>
                          satirIndex === index
                            ? { ...satir, site_y: Number(event.target.value) }
                            : satir,
                        ),
                      )
                    }
                  />
                </label>
              </div>
            </div>
          ))}
        </div>

        <div className="stage-footer">
          <p>{COPY.geriBildirim.dikkat.teknikDetaylarIkinciKatman}</p>
          <button
            className="primary-button"
            type="button"
            onClick={() => hizalamaMutation.mutate()}
            disabled={!hazir || hizalamaMutation.isPending}
          >
            {hizalamaMutation.isPending
              ? COPY.durumlar.calisiyor
              : COPY.butonlar.hizalamayiDogrula}
          </button>
        </div>
      </section>

      <section className="panel">
        <p className="panel__eyebrow">Hizalama sonucu</p>
        {planHazirligi?.yolNoktalari?.length ? (
          hizalamaDurumu?.yanit.alignment ? (
            <AlignmentOverlay
              pathPoints={planHazirligi.yolNoktalari}
              controlPoints={kontrolNoktalari}
              transform={hizalamaDurumu.yanit.alignment.transform}
            />
          ) : (
            <PlanCanvas
              pathPoints={planHazirligi.yolNoktalari}
              walls={planHazirligi.duvarlar}
              showGrid
              testId="alignment-plan-canvas"
            />
          )
        ) : (
          <p className="panel__text">{COPY.ekranlar.hizala.mesajlar.onIzlemeBekliyor}</p>
        )}
      </section>

      <details className="panel">
        <summary className="details-summary">{COPY.ortak.teknikDetaylar}</summary>
        <div className="stage-inline-meta stage-inline-meta--wide">
          <div>
            <span>{COPY.ekranlar.hizala.residualOrtalama}</span>
            <strong>{formatNumber(hizalamaDurumu?.yanit.alignment?.residual_mean_m)}</strong>
          </div>
          <div>
            <span>{COPY.ekranlar.hizala.residualMaksimum}</span>
            <strong>{formatNumber(hizalamaDurumu?.yanit.alignment?.residual_max_m)}</strong>
          </div>
          <div>
            <span>{COPY.ekranlar.hizala.donusAcisi}</span>
            <strong>{formatNumber(hizalamaDurumu?.yanit.alignment?.transform.theta_deg)}</strong>
          </div>
          <div>
            <span>{COPY.ekranlar.hizala.kaymaBilgisi}</span>
            <strong>
              {formatNumber(hizalamaDurumu?.yanit.alignment?.transform.tx_m)} /{" "}
              {formatNumber(hizalamaDurumu?.yanit.alignment?.transform.ty_m)}
            </strong>
          </div>
        </div>
      </details>
    </PageLayout>
  );
}
