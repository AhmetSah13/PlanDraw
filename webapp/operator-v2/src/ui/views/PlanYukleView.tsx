import React, { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { COPY } from "../../content";
import {
  compilePlanText,
  importDwgDosyasi,
  importDxfDosyasi,
  importJsonDosyasi,
  type PlanHazirlamaYaniti,
} from "../../data/services/operatorService";
import {
  PlanYukleDropzone,
} from "../components/PlanYukleDropzone";
import { PlanCanvas } from "../components/PlanCanvas";
import {
  useWorkflowStore,
  type PlanKaynakTuru,
} from "../../workflow/store/workflowStore";

type DosyaKaynakTuru = Exclude<PlanKaynakTuru, "manuel">;

type GirdiDurumu =
  | { etiket: string; mesaj: string; ton: "bekliyor" | "hazir" | "hata" | "calisiyor" }
  | null;

const DOSYA_KABULLERI: Record<DosyaKaynakTuru, string> = {
  dxf: ".dxf",
  dwg: ".dwg",
  json: ".json",
};

const ENDPOINT_HARITASI: Record<PlanKaynakTuru, string> = {
  dxf: "/api/import_dxf",
  dwg: "/api/import_dwg",
  json: "/api/import_plan",
  manuel: "/api/compile_plan",
};

function kaynakBilgisiGetir(kaynak: PlanKaynakTuru) {
  if (kaynak === "dxf") {
    return COPY.ekranlar.planYukle.kaynaklar.dxf;
  }
  if (kaynak === "dwg") {
    return COPY.ekranlar.planYukle.kaynaklar.dwg;
  }
  if (kaynak === "json") {
    return COPY.ekranlar.planYukle.kaynaklar.json;
  }
  return COPY.ekranlar.planYukle.kaynaklar.manuel;
}

function komutMetniBul(yanit: PlanHazirlamaYaniti) {
  const raw = typeof yanit.commands_text === "string" ? yanit.commands_text.trim() : "";
  const optimized =
    typeof yanit.commands_text_optimized === "string"
      ? yanit.commands_text_optimized.trim()
      : "";
  return optimized || raw;
}

export function PlanYukleView() {
  const hataMesaji = useWorkflowStore((state) => state.hataMesaji);
  const planHazirligi = useWorkflowStore((state) => state.planHazirligi);
  const setHataMesaji = useWorkflowStore((state) => state.setHataMesaji);
  const setPlanHazirligi = useWorkflowStore((state) => state.setPlanHazirligi);
  const setAktifAsama = useWorkflowStore((state) => state.setAktifAsama);
  const setHizalamaDurumu = useWorkflowStore((state) => state.setHizalamaDurumu);
  const setKontrolDurumu = useWorkflowStore((state) => state.setKontrolDurumu);
  const setSonucCiktisi = useWorkflowStore((state) => state.setSonucCiktisi);
  const setCalistirmaOzeti = useWorkflowStore((state) => state.setCalistirmaOzeti);
  const sifirlaSimulation = useWorkflowStore((state) => state.sifirlaSimulation);

  const [aktifKaynak, setAktifKaynak] = useState<PlanKaynakTuru>("dxf");
  const [dosyalar, setDosyalar] = useState<Record<DosyaKaynakTuru, File | null>>({
    dxf: null,
    dwg: null,
    json: null,
  });
  const [suruklemeAktif, setSuruklemeAktif] = useState(false);
  const [manuelPlanMetni, setManuelPlanMetni] = useState("");

  const planMutation = useMutation({
    mutationFn: async () => {
      if (aktifKaynak === "dxf") {
        const file = dosyalar.dxf;
        if (!file) {
          throw new Error(COPY.geriBildirim.hata.dosyaSecilmedi);
        }
        return importDxfDosyasi(file);
      }

      if (aktifKaynak === "dwg") {
        const file = dosyalar.dwg;
        if (!file) {
          throw new Error(COPY.geriBildirim.hata.dosyaSecilmedi);
        }
        return importDwgDosyasi(file);
      }

      if (aktifKaynak === "json") {
        const file = dosyalar.json;
        if (!file) {
          throw new Error(COPY.geriBildirim.hata.dosyaSecilmedi);
        }
        return importJsonDosyasi(file);
      }

      if (!manuelPlanMetni.trim()) {
        throw new Error(COPY.geriBildirim.hata.manuelPlanBos);
      }

      return compilePlanText(manuelPlanMetni);
    },
    onMutate: () => {
      setHataMesaji("");
      setPlanHazirligi(null);
      setHizalamaDurumu(null);
      setKontrolDurumu(null);
      setSonucCiktisi(null);
      setCalistirmaOzeti(null);
      sifirlaSimulation();
    },
    onSuccess: (yanit) => {
      const komutMetni = komutMetniBul(yanit);
      const okDurumu = yanit.ok !== false;

      if (!okDurumu) {
        setHataMesaji(String(yanit.error ?? COPY.geriBildirim.hata.genel));
        return;
      }

      if (!komutMetni) {
        setHataMesaji(COPY.geriBildirim.hata.komutUretilemedi);
        return;
      }

      const secilenKaynak = kaynakBilgisiGetir(aktifKaynak);
      const dosyaAdi =
        aktifKaynak === "manuel"
          ? secilenKaynak.etiket
          : dosyalar[aktifKaynak as DosyaKaynakTuru]?.name ?? secilenKaynak.etiket;

      setPlanHazirligi({
        kaynakTuru: aktifKaynak,
        kaynakEtiketi: secilenKaynak.etiket,
        endpoint: ENDPOINT_HARITASI[aktifKaynak],
        girdiAdi: dosyaAdi,
        durum: "hazir",
        mesaj: COPY.geriBildirim.basari.planHazir,
        komutMetni,
        planMetni: String(yanit.plan_text ?? (aktifKaynak === "manuel" ? manuelPlanMetni : "")),
        duvarlar: Array.isArray(yanit.walls) ? yanit.walls : [],
        yolNoktalari: Array.isArray(yanit.raw_path_points)
          ? yanit.raw_path_points
          : Array.isArray(yanit.stats?.path_points)
            ? yanit.stats.path_points
            : [],
        uyarilar: Array.isArray(yanit.warnings) ? yanit.warnings : [],
        onerilenAdimBoyutu:
          typeof yanit.recommended_step_size === "number"
            ? yanit.recommended_step_size
            : undefined,
      });
      setAktifAsama("plan-yukle");
    },
    onError: (error) => {
      setHataMesaji(String(error instanceof Error ? error.message : COPY.geriBildirim.hata.genel));
    },
  });

  const aktifKaynakBilgisi = kaynakBilgisiGetir(aktifKaynak);
  const mevcutDosya =
    aktifKaynak === "manuel" ? null : dosyalar[aktifKaynak as DosyaKaynakTuru];

  const girdiDurumu = useMemo<GirdiDurumu>(() => {
    if (planMutation.isPending) {
      return {
        etiket: COPY.durumlar.calisiyor,
        mesaj: "Kaynak işleniyor ve komut üretimi doğrulanıyor.",
        ton: "calisiyor",
      };
    }

    if (hataMesaji) {
      return {
        etiket: COPY.durumlar.hata,
        mesaj: hataMesaji,
        ton: "hata",
      };
    }

    if (planHazirligi) {
      return {
        etiket: COPY.durumlar.hazir,
        mesaj: planHazirligi.mesaj,
        ton: "hazir",
      };
    }

    return {
      etiket: COPY.durumlar.bekliyor,
      mesaj: COPY.ekranlar.planYukle.siradakiAdimBekliyor,
      ton: "bekliyor",
    };
  }, [hataMesaji, planHazirligi, planMutation.isPending]);

  return (
    <section className="plan-load-page">
      <header className="plan-load-page__hero">
        <div>
          <p className="plan-load-page__eyebrow">{COPY.ekranlar.planYukle.kaynakBasligi}</p>
          <h2>{COPY.ekranlar.planYukle.ustBaslik}</h2>
          <p className="plan-load-page__intro">{COPY.ekranlar.planYukle.ustAciklama}</p>
        </div>
        <div className="plan-load-status">
          <span className="plan-load-status__label">{COPY.ortak.calistirilabilirGirdi}</span>
          <strong>{girdiDurumu?.etiket}</strong>
          <p>{girdiDurumu?.mesaj}</p>
        </div>
      </header>

      <section className="plan-load-sources">
        {(["dxf", "dwg", "json", "manuel"] as PlanKaynakTuru[]).map((kaynak) => {
          const bilgi = kaynakBilgisiGetir(kaynak);
          const aktif = aktifKaynak === kaynak;

          return (
            <button
              key={kaynak}
              type="button"
              className={`plan-load-source-card ${aktif ? "plan-load-source-card--aktif" : ""}`}
              onClick={() => {
                setAktifKaynak(kaynak);
                setHataMesaji("");
              }}
            >
              <span className="plan-load-source-card__title">{bilgi.etiket}</span>
              <span className="plan-load-source-card__text">{bilgi.aciklama}</span>
              <span className="plan-load-source-card__format">{bilgi.formatBilgisi}</span>
            </button>
          );
        })}
      </section>

      <section className="plan-load-workspace">
        <div className="plan-load-main">
          <div className="plan-load-card">
            <p className="plan-load-card__eyebrow">{COPY.ekranlar.planYukle.anaPanelBasligi}</p>
            <h3>{aktifKaynakBilgisi.etiket}</h3>
            <p className="plan-load-card__text">{aktifKaynakBilgisi.aciklama}</p>

            {aktifKaynak === "manuel" ? (
              <div className="plan-load-manual">
                <label className="plan-load-field">
                  <span>{COPY.ekranlar.planYukle.metinEtiketi}</span>
                  <textarea
                    className="plan-load-textarea"
                    rows={10}
                    value={manuelPlanMetni}
                    placeholder={COPY.ekranlar.planYukle.metinYerTutucu}
                    onChange={(event) => setManuelPlanMetni(event.target.value)}
                  />
                </label>
                <div className="plan-load-inline-meta">
                  <div>
                    <span>{COPY.ortak.kabulEdilenFormatlar}</span>
                    <strong>{aktifKaynakBilgisi.formatBilgisi}</strong>
                  </div>
                  <div>
                    <span>{COPY.ortak.yuklemeDurumu}</span>
                    <strong>
                      {manuelPlanMetni.trim()
                        ? COPY.ekranlar.planYukle.manuelHazir
                        : COPY.ekranlar.planYukle.manuelBekliyor}
                    </strong>
                  </div>
                </div>
              </div>
            ) : (
              <PlanYukleDropzone
                aktif
                kabulBilgisi={DOSYA_KABULLERI[aktifKaynak]}
                dosya={mevcutDosya}
                suruklemeAktif={suruklemeAktif}
                yukleniyor={planMutation.isPending}
                onDosyaSec={(dosya) =>
                  setDosyalar((onceki) => ({
                    ...onceki,
                    [aktifKaynak]: dosya,
                  }))
                }
                onSuruklemeDurumu={setSuruklemeAktif}
              />
            )}

            {hataMesaji ? (
              <div className="plan-load-feedback plan-load-feedback--hata">
                <strong>{COPY.ortak.hataOzeti}</strong>
                <p>{hataMesaji}</p>
                <button
                  className="secondary-button plan-load-feedback__action"
                  type="button"
                  onClick={() => planMutation.mutate()}
                  disabled={planMutation.isPending}
                >
                  {COPY.butonlar.tekrarDene}
                </button>
              </div>
            ) : null}

            {planHazirligi ? (
              <div className="plan-load-feedback plan-load-feedback--basari">
                <strong>{COPY.ortak.basariOzeti}</strong>
                <p>{planHazirligi.mesaj}</p>
              </div>
            ) : null}

            <div className="plan-load-footer">
              <p>{COPY.geriBildirim.dikkat.teknikDetaylarIkinciKatman}</p>
              <button
                className="primary-button"
                type="button"
                onClick={() => planMutation.mutate()}
                disabled={planMutation.isPending}
              >
                {planMutation.isPending ? COPY.durumlar.calisiyor : COPY.butonlar.girdiyiHazirla}
              </button>
            </div>
          </div>

          <details className="plan-load-tech">
            <summary>{COPY.ortak.teknikDetaylar}</summary>
            <div className="plan-load-tech__body">
              <div>
                <span>{COPY.ortak.endpointBilgisi}</span>
                <strong>{ENDPOINT_HARITASI[aktifKaynak]}</strong>
              </div>
              <div>
                <span>{COPY.ortak.kabulEdilenFormatlar}</span>
                <strong>{aktifKaynakBilgisi.formatBilgisi}</strong>
              </div>
              {planHazirligi ? (
                <>
                  <div>
                    <span>Seçilen girdi</span>
                    <strong>{planHazirligi.girdiAdi}</strong>
                  </div>
                  <div>
                    <span>Üretilen komut</span>
                    <strong>{planHazirligi.komutMetni ? "Var" : "Yok"}</strong>
                  </div>
                  <div>
                    <span>Duvar sayısı</span>
                    <strong>{planHazirligi.duvarlar.length}</strong>
                  </div>
                  <div>
                    <span>Yol noktası</span>
                    <strong>{planHazirligi.yolNoktalari.length}</strong>
                  </div>
                  {typeof planHazirligi.onerilenAdimBoyutu === "number" ? (
                    <div>
                      <span>Önerilen adım boyutu</span>
                      <strong>{planHazirligi.onerilenAdimBoyutu.toFixed(3)}</strong>
                    </div>
                  ) : null}
                  {planHazirligi.uyarilar.length > 0 ? (
                    <div className="plan-load-tech__warnings">
                      <span>Uyarılar</span>
                      <ul>
                        {planHazirligi.uyarilar.map((uyari) => (
                          <li key={uyari}>{uyari}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </>
              ) : (
                <p className="plan-load-tech__empty">{COPY.geriBildirim.bos.sonucYok}</p>
              )}
            </div>
          </details>

          <section className="plan-load-preview">
            <p className="plan-load-card__eyebrow">Plan Önizleme</p>
            {planHazirligi ? (
              <PlanCanvas
                pathPoints={planHazirligi.yolNoktalari}
                walls={planHazirligi.duvarlar}
                showGrid
                testId="plan-preview-canvas"
              />
            ) : (
              <p className="panel__text">Önizleme için plan girdisi hazırlayın.</p>
            )}
          </section>
        </div>

        <aside className="plan-load-side">
          <div className={`plan-load-readiness plan-load-readiness--${girdiDurumu?.ton}`}>
            <span className="plan-load-readiness__label">{COPY.ortak.hazirOlmaDurumu}</span>
            <strong>{girdiDurumu?.etiket}</strong>
            <p>{girdiDurumu?.mesaj}</p>
          </div>

          <div className="plan-load-next">
            <span className="plan-load-next__label">{COPY.ortak.sonrakiAdim}</span>
            <strong>
              {planHazirligi ? COPY.asamalar.hizala.baslik : COPY.asamalar.planYukle.baslik}
            </strong>
            <p>
              {planHazirligi
                ? COPY.ekranlar.planYukle.siradakiAdimHazir
                : COPY.ekranlar.planYukle.siradakiAdimBekliyor}
            </p>
          </div>
        </aside>
      </section>
    </section>
  );
}
