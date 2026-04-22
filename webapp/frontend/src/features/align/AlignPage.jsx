import React, { useMemo, useState } from "react";
import StageFrame from "../../ui/StageFrame.jsx";
import { useAlignMutation } from "../../core/data/hooks.js";
import { useWorkflow } from "../../core/workflow/WorkflowProvider.jsx";

export default function AlignPage() {
  const { state, updateAlign } = useWorkflow();
  const align = useAlignMutation();
  const [rows, setRows] = useState([{ cad_x: "", cad_y: "", site_x: "", site_y: "" }, { cad_x: "", cad_y: "", site_x: "", site_y: "" }]);
  const [toleranceM, setToleranceM] = useState(0.05);
  const [error, setError] = useState("");
  const hasPipeline = Boolean(state.prepare.commandsText?.trim());

  const readinessLevel = useMemo(() => {
    if (!hasPipeline) return "blocked";
    if (align.isPending) return "running";
    if (error) return "error";
    if (state.align.alignment) return "done";
    return "ready";
  }, [align.isPending, error, hasPipeline, state.align.alignment]);

  async function runAlign() {
    setError("");
    try {
      const points = rows
        .filter((r) => Object.values(r).every((v) => String(v).trim() !== ""))
        .map((r) => ({
          cad_x: Number(r.cad_x),
          cad_y: Number(r.cad_y),
          site_x: Number(r.site_x),
          site_y: Number(r.site_y),
        }));
      const res = await align.mutateAsync({ walls: state.prepare.walls, control_points: points, tolerance_m: toleranceM });
      updateAlign({ alignment: res?.alignment ?? null, controlPoints: points });
    } catch (e) {
      setError(String(e.message ?? e));
    }
  }

  return (
    <StageFrame
      title="Align"
      lead="CAD ve saha noktalarini esleyin."
      status={readinessLevel}
      main={
        <>
          <section className="panel">
            <h2>Kontrol noktalari</h2>
            {!hasPipeline ? <div className="note">Once Prepare asamasinda komut uretin.</div> : null}
            {rows.map((row, idx) => (
              <div className="kv" key={idx}>
                <input value={row.cad_x} placeholder="CAD X" onChange={(e) => setRows((prev) => prev.map((r, i) => (i === idx ? { ...r, cad_x: e.target.value } : r)))} />
                <input value={row.cad_y} placeholder="CAD Y" onChange={(e) => setRows((prev) => prev.map((r, i) => (i === idx ? { ...r, cad_y: e.target.value } : r)))} />
                <input value={row.site_x} placeholder="SITE X" onChange={(e) => setRows((prev) => prev.map((r, i) => (i === idx ? { ...r, site_x: e.target.value } : r)))} />
                <input value={row.site_y} placeholder="SITE Y" onChange={(e) => setRows((prev) => prev.map((r, i) => (i === idx ? { ...r, site_y: e.target.value } : r)))} />
              </div>
            ))}
            <label>
              Tolerans
              <input type="number" step="0.01" value={toleranceM} onChange={(e) => setToleranceM(Number(e.target.value || 0.05))} />
            </label>
            <div className="actions">
              <button type="button" className="btn btn--primary" disabled={!hasPipeline || align.isPending} onClick={runAlign}>
                {align.isPending ? "Calisiyor..." : "Hizalamayi calistir"}
              </button>
              <button type="button" className="btn" onClick={() => setRows((prev) => [...prev, { cad_x: "", cad_y: "", site_x: "", site_y: "" }])}>
                Satir ekle
              </button>
            </div>
            {error ? <div className="note note--err">{error}</div> : null}
          </section>
        </>
      }
      side={
        <section className="panel">
          <h2>Karar</h2>
          <p>{state.align.alignment ? "Plan asamasina gecebilirsiniz." : "Hizalamayi once calistirin."}</p>
          <div className="kv">
            <div><small>Duvar</small><strong>{state.prepare.walls?.length ?? 0}</strong></div>
            <div><small>Nokta</small><strong>{state.align.controlPoints?.length ?? 0}</strong></div>
          </div>
        </section>
      }
    />
  );
}
