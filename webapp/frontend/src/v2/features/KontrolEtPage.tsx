import React from "react";
import { useMutation } from "@tanstack/react-query";
import { analizEt } from "../lib/api";
import { useWorkflowStore } from "../store/workflowStore";
import { PageScaffold } from "../components/PageScaffold";

export function KontrolEtPage() {
  const store = useWorkflowStore();
  const kontrol = useMutation({
    mutationFn: analizEt,
    onSuccess: (res: any) => {
      store.merge({
        sonKontrol: { blocked: Boolean(res.blocked), pathCount: Number(res?.stats?.path_points?.length ?? 0) },
        commandsText: res.commands_unrolled ?? store.commandsText,
        rawPathPoints: res?.stats?.path_points ?? [],
        hata: "",
      });
    },
    onError: (e: any) => store.setHata(String(e?.message ?? e)),
  });

  const hazir = store.sonKontrol && !store.sonKontrol.blocked;
  return (
    <PageScaffold
      baslik="Kontrol Et"
      aciklama="Çalıştırma öncesinde plan analizi ve engel kontrolü yapılır."
      durum={hazir ? "Hazır" : "Bekliyor"}
      aside={
        <section className="panel">
          <h3>Kontrol özeti</h3>
          <p>{hazir ? "Kontrol temiz. Çalıştır adımına geçebilirsiniz." : "Henüz kontrol tamamlanmadı veya engel var."}</p>
          <div className="kpi"><span>Path noktası</span><strong>{store.sonKontrol?.pathCount ?? 0}</strong></div>
          <div className="kpi"><span>Engel</span><strong>{store.sonKontrol?.blocked ? "var" : "yok"}</strong></div>
        </section>
      }
    >
      <section className="panel">
        <h3>Plan analizi</h3>
        <p>Bu adım optimize etmez; mevcut planı analiz edip çalıştırma uygunluğunu raporlar.</p>
        <button className="btn btn--ana" onClick={() => kontrol.mutate(store.commandsText)} disabled={kontrol.isPending || !store.commandsText}>
          {kontrol.isPending ? "Analiz çalışıyor..." : "Planı kontrol et"}
        </button>
      </section>
      {store.hata ? <div className="uyari uyari--hata">{store.hata}</div> : null}
    </PageScaffold>
  );
}
