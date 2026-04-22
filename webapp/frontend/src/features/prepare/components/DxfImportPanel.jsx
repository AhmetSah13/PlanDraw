import React from "react";
import PlanStatisticsPanel from "../../../components/PlanStatisticsPanel.jsx";

export default function DxfImportPanel({
  importBusy,
  onFileSelect,
  warnings,
  lastImport,
  previewBusy,
  previewError,
  layerPreview,
  selectedLayers,
  onToggleLayer,
  onSelectAllLayers,
  onClearLayers,
  selectedFile,
  stepSize,
  getStepAutoLabel,
  onGenerateCommands,
}) {
  let lastLine = null;
  if (lastImport && lastImport.source === "dxf" && lastImport.fileName) {
    const when = lastImport.when ? new Date(lastImport.when) : null;
    const timeLabel = when
      ? when.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit", second: "2-digit" })
      : "";
    lastLine = (
      <div className={"prepare2-import-last " + (lastImport.ok ? "prepare2-import-last--ok" : "prepare2-import-last--err")}>
        <span className="prepare2-import-last__label">{lastImport.ok ? "Yüklendi:" : "Yüklenemedi:"}</span>{" "}
        <span className="prepare2-import-last__file">{lastImport.fileName}</span>
        {timeLabel ? <span className="prepare2-import-last__time"> — {timeLabel}</span> : null}
      </div>
    );
  }
  return (
    <div className="prepare2-source-block">
      <div className="prepare2-source-block__title">DXF içe aktar</div>
      <div className="prepare2-muted prepare2-muted--sm">DXF (ASCII) — LINE / LWPOLYLINE / POLYLINE desteklenir.</div>

      <div className="prepare2-source-block__body">
        <label className={"prepare2-file" + (importBusy ? " prepare2-file--disabled" : "")}>
          <input type="file" accept=".dxf" disabled={importBusy} onChange={onFileSelect} />
          <span>Dosya seç</span>
        </label>

        {selectedFile ? <div className="prepare2-muted prepare2-muted--sm">Seçili dosya: <strong>{selectedFile.name}</strong></div> : null}
        {lastLine}

        {layerPreview && layerPreview.source === "dxf" ? (
          <div className="prepare2-muted prepare2-muted--sm">
            Önerilen adım: <strong>{Number(stepSize).toFixed(2)} m</strong> ({getStepAutoLabel(Number(stepSize))})
          </div>
        ) : null}

        <div className="prepare2-row">
          <button type="button" className="prepare2-btn prepare2-btn--primary" onClick={onGenerateCommands} disabled={importBusy || !selectedFile}>
            {importBusy ? "İşleniyor…" : "Komutları üret"}
          </button>
        </div>

        {previewError ? <div className="prepare2-inline-error">{previewError}</div> : null}
        {previewBusy ? <div className="prepare2-muted prepare2-muted--sm">Katmanlar okunuyor…</div> : null}

        {layerPreview && layerPreview.source === "dxf" && Array.isArray(layerPreview.layers) && layerPreview.layers.length > 0 ? (
          <details className="prepare2-layers" open={Boolean(selectedLayers?.length)}>
            <summary className="prepare2-layers__summary">Katman seçimi</summary>
            <div className="prepare2-layers__content">
              <div className="prepare2-muted prepare2-muted--sm">Önerilen katmanlar işaretli.</div>
              <div className="prepare2-row">
                <button type="button" className="prepare2-btn prepare2-btn--ghost" onClick={onSelectAllLayers}>
                  Hepsini seç
                </button>
                <button type="button" className="prepare2-btn prepare2-btn--ghost" onClick={onClearLayers}>
                  Temizle
                </button>
              </div>
              <div className="prepare2-layer-list" role="list">
                {layerPreview.layers.map((layer) => {
                  const checked = selectedLayers.includes(layer.name);
                  const len = Number(layer.total_length ?? 0);
                  return (
                    <label key={layer.name} className="prepare2-layer-row">
                      <span className="prepare2-layer-row__left">
                        <input type="checkbox" checked={checked} onChange={() => onToggleLayer(layer.name)} />
                        <span className="prepare2-layer-row__name">{layer.name}</span>
                      </span>
                      <span className="prepare2-layer-row__meta">
                        seg: {layer.segments ?? 0} · len: {Math.round(len)}
                      </span>
                    </label>
                  );
                })}
              </div>
            </div>
          </details>
        ) : null}

        {layerPreview && layerPreview.dxf_insight ? <PlanStatisticsPanel dxfInsight={layerPreview.dxf_insight} /> : null}
        {Array.isArray(warnings) && warnings.length > 0 ? (
          <ul className="prepare2-warn-list">
            {warnings.map((w, i) => (
              <li key={i}>{typeof w === "string" ? w : JSON.stringify(w)}</li>
            ))}
          </ul>
        ) : null}
      </div>
    </div>
  );
}
