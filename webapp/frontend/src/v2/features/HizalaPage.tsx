import React, { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { hizala } from "../lib/api";
import { useWorkflowStore } from "../store/workflowStore";
import { PageScaffold } from "../components/PageScaffold";

export function HizalaPage() {
  const store = useWorkflowStore();
  const [rows, setRows] = useState([
    { cad_x: "", cad_y: "", site_x: "", site_y: "" },
    { cad_x: "", cad_y: "", site_x: "", site_y: "" },
  ]);

  const mutation = useMutation({
    mutationFn: hizala,
    onSuccess: (res: any) => store.merge({ alignment: res.alignment ?? null, hata: "" }),
    onError: (e: any) => store.setHata(String(e?.message ?? e)),
  });

  return (
    <PageScaffold
      baslik="Hizala"
      aciklama="Plan ile saha referansını eşleştirip güvenli geçiş doğrulaması alın."
      durum={store.alignment ? "Tamamlandı" : "Bekliyor"}
      aside={
        <section className="panel">
          <h3>Durum</h3>
          <p>{store.alignment ? "Hizalama kaydı oluşturuldu." : "En az iki nokta girip hizalamayı başlatın."}</p>
          <div className="kpi"><span>Kontrol noktası</span><strong>{rows.length}</strong></div>
        </section>
      }
    >
      <section className="panel">
        <h3>Kontrol noktaları</h3>
        {rows.map((row, i) => (
          <div className="satir4" key={i}>
            <input placeholder="CAD X" value={row.cad_x} onChange={(e) => setRows((p) => p.map((r, idx) => idx === i ? { ...r, cad_x: e.target.value } : r))} />
            <input placeholder="CAD Y" value={row.cad_y} onChange={(e) => setRows((p) => p.map((r, idx) => idx === i ? { ...r, cad_y: e.target.value } : r))} />
            <input placeholder="Saha X" value={row.site_x} onChange={(e) => setRows((p) => p.map((r, idx) => idx === i ? { ...r, site_x: e.target.value } : r))} />
            <input placeholder="Saha Y" value={row.site_y} onChange={(e) => setRows((p) => p.map((r, idx) => idx === i ? { ...r, site_y: e.target.value } : r))} />
          </div>
        ))}
        <div className="aksiyonlar">
          <button className="btn" onClick={() => setRows((p) => [...p, { cad_x: "", cad_y: "", site_x: "", site_y: "" }])}>Satır ekle</button>
          <button
            className="btn btn--ana"
            disabled={mutation.isPending || !store.walls.length}
            onClick={() =>
              mutation.mutate({
                walls: store.walls,
                control_points: rows.map((r) => ({ cad_x: Number(r.cad_x), cad_y: Number(r.cad_y), site_x: Number(r.site_x), site_y: Number(r.site_y) })),
                tolerance_m: 0.05,
              })
            }
          >
            {mutation.isPending ? "Hizalanıyor..." : "Hizalamayı başlat"}
          </button>
        </div>
      </section>
      {store.hata ? <div className="uyari uyari--hata">{store.hata}</div> : null}
    </PageScaffold>
  );
}
