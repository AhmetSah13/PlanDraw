import React, { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { jobDurdur, jobOlustur, seriCalistir, streamUrl } from "../lib/api";
import { useWorkflowStore } from "../store/workflowStore";
import { PageScaffold } from "../components/PageScaffold";

export function CalistirPage() {
  const store = useWorkflowStore();
  const [mod, setMod] = useState<"simulasyon" | "canli">("simulasyon");
  const [durumMesaji, setDurumMesaji] = useState("");

  const baslat = useMutation({
    mutationFn: jobOlustur,
    onSuccess: (res) => {
      setDurumMesaji("İş başlatıldı, canlı akış dinleniyor.");
      store.merge({ jobId: res.job_id, hata: "" });
      const es = new EventSource(streamUrl(res.job_id));
      es.onmessage = (ev) => {
        try {
          const parsed = JSON.parse(ev.data);
          store.merge({ sonEvent: parsed });
        } catch {
          store.setHata("Akış verisi çözümlenemedi.");
        }
      };
      es.onerror = () => {
        es.close();
      };
    },
    onError: (e: any) => store.setHata(String(e?.message ?? e)),
  });

  const durdur = useMutation({
    mutationFn: jobDurdur,
    onSuccess: (res: any) => setDurumMesaji(res?.stopped ? "Stop başarılı: iş durduruldu." : "İş zaten tamamlanmış olabilir."),
    onError: (e: any) => {
      const msg = String(e?.message ?? "");
      if (msg.includes("job not found")) {
        setDurumMesaji("İş bulunamadı: büyük olasılıkla tamamlandı ve temizlendi.");
      } else {
        setDurumMesaji(`Gerçek hata: ${msg}`);
      }
    },
  });

  const canli = useMutation({
    mutationFn: ({ text, dryRun }: { text: string; dryRun: boolean }) => seriCalistir(text, dryRun),
    onSuccess: (res) => {
      store.merge({ serialSonuc: res });
      setDurumMesaji("Seri çalıştırma yanıtı alındı.");
    },
    onError: (e: any) => store.setHata(String(e?.message ?? e)),
  });

  const hazir = useMemo(() => !!store.commandsText && !!store.sonKontrol && !store.sonKontrol.blocked, [store.commandsText, store.sonKontrol]);

  return (
    <PageScaffold
      baslik="Çalıştır"
      aciklama="Simülasyon ve canlı gönderim ayrımı net, riskli aksiyonlar kontrollü."
      durum={hazir ? "Hazır" : "Engelli"}
      aside={
        <section className="panel">
          <h3>Çalışma durumu</h3>
          <p>{durumMesaji || "Henüz işlem başlatılmadı."}</p>
          <div className="kpi"><span>Aktif iş</span><strong>{store.jobId || "-"}</strong></div>
          <div className="kpi"><span>Son event</span><strong>{store.sonEvent ? "var" : "yok"}</strong></div>
        </section>
      }
    >
      <section className="panel">
        <h3>Mod seçimi</h3>
        <div className="aksiyonlar">
          <button className={`btn ${mod === "simulasyon" ? "btn--ana" : ""}`} onClick={() => setMod("simulasyon")}>Simülasyon</button>
          <button className={`btn ${mod === "canli" ? "btn--ana" : ""}`} onClick={() => setMod("canli")}>Canlı</button>
        </div>
        <div className="aksiyonlar">
          <button className="btn btn--ana" disabled={!hazir || baslat.isPending} onClick={() => baslat.mutate(store.commandsText)}>
            {baslat.isPending ? "Başlatılıyor..." : "İşi başlat"}
          </button>
          <button className="btn btn--risk" disabled={!store.jobId || durdur.isPending} onClick={() => durdur.mutate(store.jobId)}>
            İşi durdur
          </button>
        </div>
        {mod === "canli" ? (
          <div className="aksiyonlar">
            <button className="btn" onClick={() => canli.mutate({ text: store.commandsText, dryRun: true })}>Ön kontrol</button>
            <button className="btn btn--risk" onClick={() => canli.mutate({ text: store.commandsText, dryRun: false })}>Canlı gönder</button>
          </div>
        ) : null}
      </section>
      {store.hata ? <div className="uyari uyari--hata">{store.hata}</div> : null}
    </PageScaffold>
  );
}
