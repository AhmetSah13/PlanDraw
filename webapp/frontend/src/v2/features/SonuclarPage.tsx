import React from "react";
import { PageScaffold } from "../components/PageScaffold";
import { useWorkflowStore } from "../store/workflowStore";

export function SonuclarPage() {
  const store = useWorkflowStore();
  return (
    <PageScaffold
      baslik="Sonuçlar"
      aciklama="Önce sonuç özeti, sonra önerilen bir sonraki adım, en sonda teknik detay."
      durum={store.serialSonuc || store.sonEvent ? "Tamamlandı" : "Bekliyor"}
      aside={
        <section className="panel">
          <h3>Önerilen adım</h3>
          <p>{store.serialSonuc ? "Yeni görev için Plan Yükle adımına dönün." : "Önce Çalıştır adımında işlem başlatın."}</p>
        </section>
      }
    >
      <section className="panel">
        <h3>Sonuç özeti</h3>
        {store.serialSonuc ? <pre className="kod">{JSON.stringify(store.serialSonuc, null, 2)}</pre> : <p>Henüz sonuç yok.</p>}
      </section>
      <section className="panel">
        <h3>Canlı akış son verisi</h3>
        {store.sonEvent ? <pre className="kod">{JSON.stringify(store.sonEvent, null, 2)}</pre> : <p>Henüz event alınmadı.</p>}
      </section>
    </PageScaffold>
  );
}
