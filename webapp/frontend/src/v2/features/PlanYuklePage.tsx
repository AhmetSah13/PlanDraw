import React from "react";
import { useMutation } from "@tanstack/react-query";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { compilePlan, importDwg, importDxf, importPlanJson } from "../lib/api";
import { useWorkflowStore } from "../store/workflowStore";
import { FileDropzone } from "../components/FileDropzone";
import { PageScaffold } from "../components/PageScaffold";

const schema = z.object({ planText: z.string().min(1, "Plan metni boş olamaz.") });

export function PlanYuklePage() {
  const store = useWorkflowStore();
  const form = useForm<{ planText: string }>({
    resolver: zodResolver(schema),
    defaultValues: { planText: store.planText },
  });

  const onError = (e: any) => store.setHata(String(e?.message ?? e));
  const dxfMutation = useMutation({ mutationFn: importDxf, onSuccess: (res: any) => store.merge({ commandsText: res.commands_text ?? "", walls: res.walls ?? [], rawPathPoints: res.raw_path_points ?? [], hata: "" }), onError });
  const dwgMutation = useMutation({ mutationFn: importDwg, onSuccess: (res: any) => store.merge({ commandsText: res.commands_text ?? "", walls: res.walls ?? [], rawPathPoints: res.raw_path_points ?? [], hata: "" }), onError });
  const jsonMutation = useMutation({ mutationFn: importPlanJson, onSuccess: (res: any) => store.merge({ commandsText: res.commands_text ?? "", walls: res.walls ?? [], rawPathPoints: res.raw_path_points ?? [], hata: "" }), onError });
  const compileMutation = useMutation({ mutationFn: compilePlan, onSuccess: (res: any) => store.merge({ commandsText: res.commands_text ?? "", walls: res.walls ?? [], rawPathPoints: res.raw_path_points ?? [], hata: "" }), onError });

  return (
    <PageScaffold
      baslik="Plan Yükle"
      aciklama="Tek hedef: geçerli bir kaynak yükleyip çalıştırılabilir komut üretmek."
      durum={store.commandsText ? "Hazır" : "Bekliyor"}
      aside={
        <section className="panel">
          <h3>Karar</h3>
          <p>{store.commandsText ? "Komut üretildi. Hizala adımına geçebilirsiniz." : "Önce kaynak yükleyin veya metni derleyin."}</p>
          <div className="kpi"><span>Komut</span><strong>{store.commandsText ? "var" : "yok"}</strong></div>
          <div className="kpi"><span>Duvar</span><strong>{store.walls.length}</strong></div>
        </section>
      }
    >
      <section className="panel">
        <h3>Dosya yükleme</h3>
        <div className="ucKolon">
          <FileDropzone accept=".dxf" label="DXF Yükle" yardim="Mimari çizim için önerilen format." onFile={(f) => dxfMutation.mutate(f)} yukleniyor={dxfMutation.isPending} />
          <FileDropzone accept=".dwg" label="DWG Yükle" yardim="DWG içeriği dönüştürülerek işlenir." onFile={(f) => dwgMutation.mutate(f)} yukleniyor={dwgMutation.isPending} />
          <FileDropzone
            accept=".json"
            label="JSON Yükle"
            yardim="Normalize plan sözleşmesi ile içe aktarılır."
            onFile={async (f) => {
              try {
                const payload = JSON.parse(await f.text());
                jsonMutation.mutate(payload);
              } catch {
                store.setHata("JSON dosyası okunamadı. Geçerli bir plan dosyası seçin.");
              }
            }}
            yukleniyor={jsonMutation.isPending}
          />
        </div>
      </section>
      <section className="panel">
        <h3>Manuel plan metni</h3>
        <form
          onSubmit={form.handleSubmit((v) => {
            store.merge({ planText: v.planText });
            compileMutation.mutate(v.planText);
          })}
        >
          <textarea {...form.register("planText")} rows={8} placeholder="LINE 0 0 100 0" />
          {form.formState.errors.planText ? <div className="uyari uyari--hata">{form.formState.errors.planText.message}</div> : null}
          <button className="btn btn--ana" type="submit" disabled={compileMutation.isPending}>{compileMutation.isPending ? "Derleniyor..." : "Planı derle"}</button>
        </form>
      </section>
      {store.hata ? <div className="uyari uyari--hata">{store.hata}</div> : null}
    </PageScaffold>
  );
}
