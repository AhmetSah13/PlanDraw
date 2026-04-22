import React, { useMemo, useState } from "react";
import StageFrame from "../../ui/StageFrame.jsx";
import {
  useAnalyzeMutation,
  useCompilePlanMutation,
  useImportDwgMutation,
  useImportDxfMutation,
  useImportJsonMutation,
} from "../../core/data/hooks.js";
import { useWorkflow } from "../../core/workflow/WorkflowProvider.jsx";

export default function PreparePage() {
  const { state, updatePrepare } = useWorkflow();
  const [showTech, setShowTech] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const importDxf = useImportDxfMutation();
  const importDwg = useImportDwgMutation();
  const importJson = useImportJsonMutation();
  const compilePlan = useCompilePlanMutation();
  const analyze = useAnalyzeMutation();
  const p = state.prepare;

  const readinessLevel = useMemo(() => {
    if (error) return "error";
    if (importDxf.isPending || importDwg.isPending || importJson.isPending || compilePlan.isPending) return "running";
    if (!p.commandsText?.trim()) return "blocked";
    return "ready";
  }, [compilePlan.isPending, error, importDwg.isPending, importDxf.isPending, importJson.isPending, p.commandsText]);

  async function importFile(kind, file) {
    if (!file) return;
    setError("");
    setInfo("");
    try {
      const fn = kind === "dxf" ? importDxf.mutateAsync : kind === "dwg" ? importDwg.mutateAsync : importJson.mutateAsync;
      const res = await fn(file);
      updatePrepare({
        source: kind,
        commandsText: res.commands_text ?? "",
        walls: res.walls ?? [],
        rawPath: res.raw_path_points ?? [],
      });
      setInfo("Icerik alindi ve komutlar guncellendi.");
    } catch (e) {
      setError(String(e.message ?? e));
    }
  }

  async function compileManual() {
    setError("");
    setInfo("");
    try {
      const res = await compilePlan.mutateAsync(p.planText);
      updatePrepare({
        source: "manual",
        commandsText: res.commands_text ?? "",
        walls: res.walls ?? [],
        rawPath: res.raw_path_points ?? [],
      });
      setInfo("Manuel plan derlendi.");
    } catch (e) {
      setError(String(e.message ?? e));
    }
  }

  async function validate() {
    setError("");
    setInfo("");
    try {
      const res = await analyze.mutateAsync(p.commandsText);
      const blocked = Boolean(res?.blocked);
      setInfo(blocked ? "Dogrulama engel bildirdi." : "Dogrulama temiz.");
    } catch (e) {
      setError(String(e.message ?? e));
    }
  }

  return (
    <StageFrame
      title="Prepare"
      lead="Kaynak secin, komut uretin ve dogrulayin."
      status={readinessLevel}
      main={
        <>
          <section className="panel">
            <h2>Kaynak</h2>
            <p>DXF, DWG, JSON veya manuel LINE metni kullanin.</p>
            <div className="kv">
              <div>
                <small>DXF</small>
                <input type="file" accept=".dxf" onChange={(e) => importFile("dxf", e.target.files?.[0])} />
              </div>
              <div>
                <small>DWG</small>
                <input type="file" accept=".dwg" onChange={(e) => importFile("dwg", e.target.files?.[0])} />
              </div>
              <div>
                <small>JSON</small>
                <input type="file" accept=".json" onChange={(e) => importFile("json", e.target.files?.[0])} />
              </div>
            </div>
            <textarea
              className="mono"
              rows={8}
              placeholder="LINE x1 y1 x2 y2"
              value={p.planText}
              onChange={(e) => updatePrepare({ planText: e.target.value })}
            />
            <div className="actions">
              <button className="btn btn--primary" type="button" onClick={compileManual} disabled={compilePlan.isPending}>
                {compilePlan.isPending ? "Derleniyor..." : "Manuel plani derle"}
              </button>
            </div>
            {error ? <div className="note note--err">{error}</div> : null}
            {info ? <div className="note note--ok">{info}</div> : null}
          </section>
          <section className="panel">
            <h2>Ozet</h2>
            <div className="kv">
              <div><small>Walls</small><strong>{Array.isArray(p.walls) ? p.walls.length : 0}</strong></div>
              <div><small>Path</small><strong>{Array.isArray(p.rawPath) ? p.rawPath.length : 0}</strong></div>
            </div>
          </section>
        </>
      }
      side={
        <>
          <section className="panel">
            <h2>Karar</h2>
            <p>{p.commandsText?.trim() ? "Align asamasina gecebilirsiniz." : "Once komut olusturun."}</p>
            <div className="actions">
              <button className="btn btn--primary" type="button" onClick={validate} disabled={analyze.isPending || !p.commandsText?.trim()}>
                {analyze.isPending ? "Kontrol..." : "Hazirligi dogrula"}
              </button>
              <button className="btn" type="button" onClick={() => setShowTech((v) => !v)}>
                {showTech ? "Teknigi gizle" : "Teknigi ac"}
              </button>
            </div>
          </section>
          {showTech ? (
            <section className="panel">
              <h2>Teknik</h2>
              <pre className="mono">{p.commandsText || "(komut yok)"}</pre>
            </section>
          ) : null}
        </>
      }
    />
  );
}
