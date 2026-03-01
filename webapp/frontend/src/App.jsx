import React, { useCallback, useMemo, useRef, useState, useEffect } from "react";
import { analyzeScenario, createJob, getJobStream, stopJob, compilePlan, exportRobot, importPlanFromJson, importDxf, importDwg } from "./api.js";
import StepperNav from "./components/StepperNav.jsx";
import StatusBanner from "./components/StatusBanner.jsx";
import AdvancedAccordion from "./components/AdvancedAccordion.jsx";
import MetricsGrid from "./components/MetricsGrid.jsx";

const DEFAULT_SCRIPT = `# name: quick_test
# units: WORLD
SPEED 120
PEN DOWN
REPEAT 4
  FORWARD 100
  TURN 90
END
PEN UP
`;

const PLAN_STORAGE_KEY = "plandraw_plans_v1";
const EXPORT_FORMAT_STORAGE_KEY = "plandraw_export_format_v1";

const DEFAULT_PLAN = `# square room
LINE 0 0 200 0
LINE 200 0 200 200
LINE 200 200 0 200
LINE 0 200 0 0
`;

const L_CORRIDOR_PLAN = `# L corridor
LINE 0 0 150 0
LINE 150 0 150 80
LINE 150 80 250 80
LINE 250 80 250 200
LINE 250 200 0 200
LINE 0 200 0 0
`;

const DEFAULT_TEMPLATES = [
  { id: "template-square", name: "Square room", plan_text: DEFAULT_PLAN, options: { step_size: 5, speed: 120, world_scale: 1, world_offset: [0, 0] }, updated_at: new Date().toISOString() },
  { id: "template-l", name: "L corridor", plan_text: L_CORRIDOR_PLAN, options: { step_size: 5, speed: 120, world_scale: 1, world_offset: [0, 0] }, updated_at: new Date().toISOString() }
];

function Badge({ ok, text }) {
  const style = {
    display: "inline-block",
    padding: "4px 10px",
    borderRadius: 999,
    fontSize: 12,
    border: "1px solid #333",
    background: ok ? "#103d25" : "#3d1010",
    color: "#fff",
    marginLeft: 8
  };
  return <span style={style}>{text}</span>;
}

function DiagList({ title, items }) {
  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ fontWeight: 700, marginBottom: 6 }}>{title}</div>
      <div style={{ maxHeight: 220, overflow: "auto", border: "1px solid #333", borderRadius: 8, padding: 8 }}>
        {items.length === 0 ? (
          <div style={{ opacity: 0.7 }}>Yok</div>
        ) : (
          items.map((d, idx) => (
            <div key={idx} style={{ marginBottom: 8 }}>
              <div>
                <b>{d.severity}</b> line {d.line}: {d.message}
              </div>
              {d.text ? <div style={{ opacity: 0.8, fontFamily: "monospace" }}>{d.text}</div> : null}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

const MARGIN = 40;
const MIN_SCALE = 0.05;
const MAX_SCALE = 200;

function computeFitView(bounds, canvasW, canvasH, margin = 40) {
  if (!bounds || bounds.length !== 4) {
    return { scale: 1, offsetX: canvasW / 2, offsetY: canvasH / 2 };
  }
  let [minx, miny, maxx, maxy] = bounds;
  if (maxx - minx < 1e-9) maxx = minx + 1;
  if (maxy - miny < 1e-9) maxy = miny + 1;
  const scale = Math.min(
    (canvasW - 2 * margin) / (maxx - minx),
    (canvasH - 2 * margin) / (maxy - miny)
  );
  const centerWorldX = (minx + maxx) / 2;
  const centerWorldY = (miny + maxy) / 2;
  const centerScreenX = canvasW / 2;
  const centerScreenY = canvasH / 2;
  const offsetX = centerScreenX - centerWorldX * scale;
  const offsetY = centerScreenY + centerWorldY * scale;
  return { scale, offsetX, offsetY };
}

function resetView(canvasW, canvasH) {
  return { scale: 1, offsetX: canvasW / 2, offsetY: canvasH / 2 };
}

function formatSecondsShort(value) {
  if (value == null) return "—";
  const v = Number(value);
  if (!Number.isFinite(v)) return "—";
  return `${v.toFixed(1)} s`;
}

function formatNumberCompact(value, maxFraction = 2) {
  if (value == null) return "—";
  const v = Number(value);
  if (!Number.isFinite(v)) return "—";
  if (Math.abs(v) >= 1000) return v.toFixed(0);
  if (Math.abs(v) >= 100) return v.toFixed(1);
  return v.toFixed(maxFraction);
}

function formatBoundsHuman(bounds) {
  if (!bounds || bounds.length !== 4) return "—";
  const [minx, miny, maxx, maxy] = bounds;
  const width = maxx - minx;
  const height = maxy - miny;
  return `${formatNumberCompact(width, 1)} × ${formatNumberCompact(height, 1)}`;
}

function StatusPillLarge({ status }) {
  const s = status === "WARN" ? "warn" : status === "BLOCKED" ? "blocked" : "safe";
  const bg = s === "safe" ? "#022c22" : s === "warn" ? "#422c02" : "#3b0a0a";
  const border = s === "safe" ? "#16a34a" : s === "warn" ? "#eab308" : "#f97373";
  const color = s === "safe" ? "#bbf7d0" : s === "warn" ? "#fef08a" : "#fecaca";
  const label = s === "safe" ? "✅ SAFE" : s === "warn" ? "⚠ WARN" : "⛔ BLOCKED";
  const guidance =
    s === "safe"
      ? "Hazır. Çizime geçebilirsiniz."
      : s === "warn"
        ? "Çizilebilir ama uyarılar var. İstersen çizime geç, istersen Plan'da ayarları değiştir."
        : "Bu ayarlarla güvenli değil. Aşağıdan bir seçenek seçin.";
  return (
    <div style={{ textAlign: "center" }}>
      <div style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", padding: "8px 18px", borderRadius: 999, border: `1px solid ${border}`, background: bg, color, fontWeight: 800, fontSize: 16, letterSpacing: 0.4 }}>
        {label}
      </div>
      <div style={{ marginTop: 8, fontSize: 13, opacity: 0.9 }}>{guidance}</div>
    </div>
  );
}

function Accordion({ title, subtitle, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div
      style={{
        border: "1px solid #333",
        borderRadius: 12,
        padding: 12,
        background: "#151515",
        boxShadow: "0 10px 25px rgba(0,0,0,0.45)"
      }}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 8,
          background: "transparent",
          border: "none",
          padding: 0,
          color: "#eee",
          cursor: "pointer"
        }}
      >
        <div>
          <div style={{ fontWeight: 800, fontSize: 14 }}>{title}</div>
          {subtitle ? <div style={{ fontSize: 11, opacity: 0.7, marginTop: 2 }}>{subtitle}</div> : null}
        </div>
        <span style={{ fontSize: 16 }}>{open ? "▾" : "▸"}</span>
      </button>
      {open && <div style={{ marginTop: 10, fontSize: 12 }}>{children}</div>}
    </div>
  );
}

function PlanSourceSelector({ selectedSource, onChange }) {
  const base = { padding: "6px 12px", borderRadius: 8, border: "1px solid #444", background: "#222", color: "#eee", cursor: "pointer", fontSize: 13 };
  const active = { ...base, background: "#1d3b7a" };
  return (
    <div style={{ display: "flex", gap: 4, marginBottom: 12 }}>
      <button type="button" style={selectedSource === "dxf" ? active : base} onClick={() => onChange("dxf")}>DXF</button>
      <button type="button" style={selectedSource === "dwg" ? active : base} onClick={() => onChange("dwg")}>DWG</button>
      <button type="button" style={selectedSource === "json" ? active : base} onClick={() => onChange("json")}>JSON</button>
      <button type="button" style={selectedSource === "manual" ? active : base} onClick={() => onChange("manual")}>Manuel (LINE)</button>
    </div>
  );
}

function DxfImportPanel({
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
    const timeLabel = when ? when.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "";
    lastLine = (
      <div style={{ marginTop: 6, fontSize: 11, color: lastImport.ok ? "#22c55e" : "#f97373" }}>
        {lastImport.ok ? "✅ Yüklendi: " : "❌ Yüklenemedi: "}
        <span>{lastImport.fileName}</span>
        {timeLabel && <span style={{ opacity: 0.8 }}> — {timeLabel}</span>}
      </div>
    );
  }
  return (
    <div style={{ marginBottom: 12, padding: "8px 10px", background: "#111", borderRadius: 8, border: "1px solid #333" }}>
      <div style={{ fontWeight: 700, marginBottom: 6 }}>DXF ile içe aktar</div>
      <label style={{ display: "flex", alignItems: "center", gap: 6, cursor: importBusy ? "not-allowed" : "pointer", opacity: importBusy ? 0.7 : 1 }}>
        <input type="file" accept=".dxf" disabled={importBusy} onChange={onFileSelect} style={{ fontSize: 12 }} />
        <span style={{ fontSize: 13 }}>Dosya seç</span>
      </label>
      {selectedFile && (
        <div style={{ marginTop: 4, fontSize: 11, opacity: 0.9 }}>Seçili dosya: {selectedFile.name}</div>
      )}
      {selectedFile && (
        <div style={{ marginTop: 8, display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <button
            type="button"
            onClick={onGenerateCommands}
            disabled={importBusy}
            style={{ padding: "6px 12px", borderRadius: 6, border: "1px solid #444", background: importBusy ? "#222" : "#166534", color: "#fff", fontSize: 12, cursor: importBusy ? "not-allowed" : "pointer", fontWeight: 600 }}
          >
            {importBusy ? "Oluşturuluyor…" : "Komutları oluştur"}
          </button>
        </div>
      )}
      {layerPreview && layerPreview.source === "dxf" && (
        <div style={{ marginTop: 4, fontSize: 11, opacity: 0.85 }}>
          Auto step: {Number(stepSize).toFixed(2)}m ({getStepAutoLabel(Number(stepSize))})
        </div>
      )}
      <div style={{ marginTop: 6, fontSize: 11, opacity: 0.85 }}>DXF (ASCII) — LINE / LWPOLYLINE / POLYLINE desteklenir</div>
      {lastLine}
      {previewError && (
        <div style={{ marginTop: 6, fontSize: 12, color: "#ff7070" }}>{previewError}</div>
      )}
      {previewBusy && (
        <div style={{ marginTop: 6, fontSize: 11, color: "#a3a3a3" }}>Katmanlar okunuyor…</div>
      )}
      {layerPreview && layerPreview.source === "dxf" && Array.isArray(layerPreview.layers) && layerPreview.layers.length > 0 && (
        <div style={{ marginTop: 8, fontSize: 12 }}>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>Katman seç</div>
          <div style={{ fontSize: 11, opacity: 0.8, marginBottom: 4 }}>Önerilen katmanlar işaretli.</div>
          <div style={{ display: "flex", gap: 6, marginBottom: 4, flexWrap: "wrap" }}>
            <button
              type="button"
              onClick={onSelectAllLayers}
              style={{ padding: "3px 8px", borderRadius: 6, border: "1px solid #444", background: "#222", color: "#eee", fontSize: 11, cursor: "pointer" }}
            >
              Hepsini seç
            </button>
            <button
              type="button"
              onClick={onClearLayers}
              style={{ padding: "3px 8px", borderRadius: 6, border: "1px solid #444", background: "#222", color: "#eee", fontSize: 11, cursor: "pointer" }}
            >
              Temizle
            </button>
          </div>
          <div style={{ maxHeight: 140, overflow: "auto", border: "1px solid #333", borderRadius: 6, padding: 6, marginBottom: 4 }}>
            {layerPreview.layers.map((layer) => {
              const checked = selectedLayers.includes(layer.name);
              const len = Number(layer.total_length ?? 0);
              return (
                <label key={layer.name} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 11, padding: "2px 0" }}>
                  <span>
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => onToggleLayer(layer.name)}
                      style={{ marginRight: 6 }}
                    />
                    {layer.name}
                  </span>
                  <span style={{ opacity: 0.8 }}>
                    seg: {layer.segments ?? 0}, len: {Math.round(len)}
                  </span>
                </label>
              );
            })}
          </div>
        </div>
      )}
      {warnings.length > 0 && (
        <ul style={{ margin: "8px 0 0 0", paddingLeft: 18, fontSize: 12, color: "#eab308" }}>
          {warnings.map((w, i) => <li key={i}>{typeof w === "string" ? w : JSON.stringify(w)}</li>)}
        </ul>
      )}
    </div>
  );
}

function DwgImportPanel({
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
  if (lastImport && lastImport.source === "dwg" && lastImport.fileName) {
    const when = lastImport.when ? new Date(lastImport.when) : null;
    const timeLabel = when ? when.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "";
    lastLine = (
      <div style={{ marginTop: 6, fontSize: 11, color: lastImport.ok ? "#22c55e" : "#f97373" }}>
        {lastImport.ok ? "✅ Yüklendi: " : "❌ Yüklenemedi: "}
        <span>{lastImport.fileName}</span>
        {timeLabel && <span style={{ opacity: 0.8 }}> — {timeLabel}</span>}
      </div>
    );
  }
  return (
    <div style={{ marginBottom: 12, padding: "8px 10px", background: "#111", borderRadius: 8, border: "1px solid #333" }}>
      <div style={{ fontWeight: 700, marginBottom: 6 }}>DWG ile içe aktar</div>
      <label style={{ display: "flex", alignItems: "center", gap: 6, cursor: importBusy ? "not-allowed" : "pointer", opacity: importBusy ? 0.7 : 1 }}>
        <input type="file" accept=".dwg" disabled={importBusy} onChange={onFileSelect} style={{ fontSize: 12 }} />
        <span style={{ fontSize: 13 }}>Dosya seç</span>
      </label>
      {selectedFile && (
        <div style={{ marginTop: 4, fontSize: 11, opacity: 0.9 }}>Seçili dosya: {selectedFile.name}</div>
      )}
      {selectedFile && (
        <div style={{ marginTop: 8, display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <button
            type="button"
            onClick={onGenerateCommands}
            disabled={importBusy}
            style={{ padding: "6px 12px", borderRadius: 6, border: "1px solid #444", background: importBusy ? "#222" : "#166534", color: "#fff", fontSize: 12, cursor: importBusy ? "not-allowed" : "pointer", fontWeight: 600 }}
          >
            {importBusy ? "Oluşturuluyor…" : "Komutları oluştur"}
          </button>
        </div>
      )}
      {layerPreview && layerPreview.source === "dwg" && (
        <div style={{ marginTop: 4, fontSize: 11, opacity: 0.85 }}>
          Auto step: {Number(stepSize).toFixed(2)}m ({getStepAutoLabel(Number(stepSize))})
        </div>
      )}
      <div style={{ marginTop: 6, fontSize: 11, opacity: 0.85 }}>DWG — dönüştürme ile DXF'e çevrilir (converter gerekir)</div>
      {lastLine}
      {previewError && (
        <div style={{ marginTop: 6, fontSize: 12, color: "#ff7070" }}>{previewError}</div>
      )}
      {previewBusy && (
        <div style={{ marginTop: 6, fontSize: 11, color: "#a3a3a3" }}>Katmanlar okunuyor…</div>
      )}
      {layerPreview && layerPreview.source === "dwg" && Array.isArray(layerPreview.layers) && layerPreview.layers.length > 0 && (
        <div style={{ marginTop: 8, fontSize: 12 }}>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>Katman seç</div>
          <div style={{ fontSize: 11, opacity: 0.8, marginBottom: 4 }}>Önerilen katmanlar işaretli.</div>
          <div style={{ display: "flex", gap: 6, marginBottom: 4, flexWrap: "wrap" }}>
            <button
              type="button"
              onClick={onSelectAllLayers}
              style={{ padding: "3px 8px", borderRadius: 6, border: "1px solid #444", background: "#222", color: "#eee", fontSize: 11, cursor: "pointer" }}
            >
              Hepsini seç
            </button>
            <button
              type="button"
              onClick={onClearLayers}
              style={{ padding: "3px 8px", borderRadius: 6, border: "1px solid #444", background: "#222", color: "#eee", fontSize: 11, cursor: "pointer" }}
            >
              Temizle
            </button>
          </div>
          <div style={{ maxHeight: 140, overflow: "auto", border: "1px solid #333", borderRadius: 6, padding: 6, marginBottom: 4 }}>
            {layerPreview.layers.map((layer) => {
              const checked = selectedLayers.includes(layer.name);
              const len = Number(layer.total_length ?? 0);
              return (
                <label key={layer.name} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 11, padding: "2px 0" }}>
                  <span>
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => onToggleLayer(layer.name)}
                      style={{ marginRight: 6 }}
                    />
                    {layer.name}
                  </span>
                  <span style={{ opacity: 0.8 }}>
                    seg: {layer.segments ?? 0}, len: {Math.round(len)}
                  </span>
                </label>
              );
            })}
          </div>
        </div>
      )}
      {warnings.length > 0 && (
        <ul style={{ margin: "8px 0 0 0", paddingLeft: 18, fontSize: 12, color: "#eab308" }}>
          {warnings.map((w, i) => <li key={i}>{typeof w === "string" ? w : JSON.stringify(w)}</li>)}
        </ul>
      )}
    </div>
  );
}

function JsonImportPanel({ importBusy, onFileSelect, onLoadSample, warnings, lastImport }) {
  let lastLine = null;
  if (lastImport && lastImport.source === "json" && lastImport.fileName) {
    const when = lastImport.when ? new Date(lastImport.when) : null;
    const timeLabel = when ? when.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "";
    lastLine = (
      <div style={{ marginTop: 6, fontSize: 11, color: lastImport.ok ? "#22c55e" : "#f97373" }}>
        {lastImport.ok ? "✅ Yüklendi: " : "❌ Yüklenemedi: "}
        <span>{lastImport.fileName}</span>
        {timeLabel && <span style={{ opacity: 0.8 }}> — {timeLabel}</span>}
      </div>
    );
  }
  return (
    <div style={{ marginBottom: 12, padding: "8px 10px", background: "#111", borderRadius: 8, border: "1px solid #333" }}>
      <div style={{ fontWeight: 700, marginBottom: 6 }}>JSON ile içe aktar</div>
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8 }}>
        <label style={{ display: "flex", alignItems: "center", gap: 6, cursor: importBusy ? "not-allowed" : "pointer", opacity: importBusy ? 0.7 : 1 }}>
          <input type="file" accept=".json" disabled={importBusy} onChange={onFileSelect} style={{ fontSize: 12 }} />
          <span style={{ fontSize: 13 }}>Dosya seç</span>
        </label>
        <button type="button" onClick={onLoadSample} disabled={importBusy} style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #444", background: "#333", color: "#eee", cursor: importBusy ? "not-allowed" : "pointer", fontSize: 12 }}>Örnek JSON yükle</button>
      </div>
      {lastLine}
      {warnings.length > 0 && (
        <ul style={{ margin: "8px 0 0 0", paddingLeft: 18, fontSize: 12, color: "#eab308" }}>
          {warnings.map((w, i) => <li key={i}>{typeof w === "string" ? w : JSON.stringify(w)}</li>)}
        </ul>
      )}
    </div>
  );
}

function LinePlanEditor({ planText, onChange, onGenerateScript, compileBusy, importBusy, compileError }) {
  return (
    <>
      <div style={{ fontWeight: 700, marginBottom: 8 }}>Plan metni (LINE x1 y1 x2 y2)</div>
      <textarea
        value={planText}
        onChange={(e) => onChange(e.target.value)}
        spellCheck={false}
        style={{ width: "100%", height: 200, borderRadius: 8, border: "1px solid #333", background: "#0b0b0b", color: "#eee", padding: 10, fontFamily: "monospace", fontSize: 13 }}
      />
      <div style={{ marginTop: 10 }}>
        <button
          onClick={onGenerateScript}
          disabled={compileBusy || importBusy}
          style={{ padding: "8px 14px", borderRadius: 8, border: "1px solid #444", background: (compileBusy || importBusy) ? "#222" : "#166534", color: "#fff", cursor: (compileBusy || importBusy) ? "not-allowed" : "pointer", fontWeight: 600 }}
        >
          {compileBusy ? "Oluşturuluyor…" : importBusy ? "İçe aktarılıyor…" : "Komutları oluştur"}
        </button>
      </div>
      {compileError ? <div style={{ marginTop: 10, color: "#ff7070" }}>{compileError}</div> : null}
    </>
  );
}

function GeneratedScriptPanel({ scriptContent, advancedOpen, onToggleAdvanced, rawContent, optimizedContent, scriptViewTab, onSelectScriptTab }) {
  const displayContent = !advancedOpen ? (optimizedContent || scriptContent) : (scriptViewTab === "raw" ? (rawContent || scriptContent) : (optimizedContent || scriptContent));
  return (
    <div style={{ border: "1px solid #333", borderRadius: 12, padding: 12 }}>
      <div style={{ fontWeight: 700, marginBottom: 8 }}>Oluşturulan çizim komutları</div>
      <button type="button" onClick={onToggleAdvanced} style={{ marginBottom: 8, padding: "4px 8px", borderRadius: 6, border: "1px solid #444", background: "#222", color: "#aaa", cursor: "pointer", fontSize: 12 }}>
        {advancedOpen ? "Gelişmiş ▾" : "Gelişmiş ▸"}
      </button>
      {advancedOpen && (
        <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
          <button type="button" onClick={() => onSelectScriptTab("raw")} style={{ padding: "4px 10px", borderRadius: 6, border: "1px solid #444", background: scriptViewTab === "raw" ? "#1d3b7a" : "#222", color: "#fff", cursor: "pointer", fontSize: 12 }}>Raw script</button>
          <button type="button" onClick={() => onSelectScriptTab("optimized")} style={{ padding: "4px 10px", borderRadius: 6, border: "1px solid #444", background: scriptViewTab === "optimized" ? "#1d3b7a" : "#222", color: "#fff", cursor: "pointer", fontSize: 12 }}>Optimized script</button>
        </div>
      )}
      <textarea
        readOnly
        value={displayContent || ""}
        style={{ width: "100%", height: 320, borderRadius: 8, border: "1px solid #333", background: "#0b0b0b", color: "#eee", padding: 10, fontFamily: "monospace", fontSize: 12 }}
      />
    </div>
  );
}

function AdvancedOptionsPanel({ open, onToggle, stepSize, setStepSize, planSpeed, setPlanSpeed, worldScale, setWorldScale, worldOffsetX, setWorldOffsetX, worldOffsetY, setWorldOffsetY }) {
  return (
    <div style={{ marginTop: 12 }}>
      <button type="button" onClick={onToggle} style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #444", background: "#222", color: "#aaa", cursor: "pointer", fontSize: 12 }}>
        {open ? "Gelişmiş ayarlar ▾" : "Gelişmiş ayarlar"}
      </button>
      {open && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginTop: 10, alignItems: "center" }}>
          <label style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{ width: 72 }}>step_size</span>
            <input type="number" min={0.1} step={0.5} value={stepSize} onChange={(e) => setStepSize(Number(e.target.value))} style={{ width: 56, padding: 4, background: "#222", color: "#eee", border: "1px solid #444" }} />
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{ width: 72 }}>speed</span>
            <input type="number" min={1} value={planSpeed} onChange={(e) => setPlanSpeed(Number(e.target.value))} style={{ width: 56, padding: 4, background: "#222", color: "#eee", border: "1px solid #444" }} />
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{ width: 72 }}>world_scale</span>
            <input type="number" min={0.01} step={0.1} value={worldScale} onChange={(e) => setWorldScale(Number(e.target.value))} style={{ width: 56, padding: 4, background: "#222", color: "#eee", border: "1px solid #444" }} />
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{ width: 72 }}>offset X</span>
            <input type="number" value={worldOffsetX} onChange={(e) => setWorldOffsetX(Number(e.target.value))} style={{ width: 56, padding: 4, background: "#222", color: "#eee", border: "1px solid #444" }} />
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{ width: 72 }}>offset Y</span>
            <input type="number" value={worldOffsetY} onChange={(e) => setWorldOffsetY(Number(e.target.value))} style={{ width: 56, padding: 4, background: "#222", color: "#eee", border: "1px solid #444" }} />
          </label>
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [script, setScript] = useState(DEFAULT_SCRIPT);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [step, setStep] = useState("plan");

  const [simRunning, setSimRunning] = useState(false);
  const simAbortRef = useRef(null);
  const [speedMultiplier, setSpeedMultiplier] = useState(1.0);
  const [tickState, setTickState] = useState(null);
  const traceRef = useRef([]);
  const canvasRef = useRef(null);
  const boundsRef = useRef(null);
  const viewRef = useRef(resetView(600, 400));
  const tickStateRef = useRef(null);
  const panStartRef = useRef(null);
  const skippedClickRef = useRef(false);
  const jobIdRef = useRef(null);
  const [simulateError, setSimulateError] = useState("");
  const [blockedSim, setBlockedSim] = useState(null);
  const queueRef = useRef([]);
  const rafIdRef = useRef(null);

  const [planText, setPlanText] = useState(DEFAULT_PLAN);
  const [stepSize, setStepSize] = useState(5);
  const [planSpeed, setPlanSpeed] = useState(120);
  const [worldScale, setWorldScale] = useState(1);
  const [worldOffsetX, setWorldOffsetX] = useState(0);
  const [worldOffsetY, setWorldOffsetY] = useState(0);
  const [compileBusy, setCompileBusy] = useState(false);
  const [compileError, setCompileError] = useState("");
  const [importBusy, setImportBusy] = useState(false);
  const [importWarnings, setImportWarnings] = useState([]);
  const [importSuccessMessage, setImportSuccessMessage] = useState("");
  const [lastImport, setLastImport] = useState(null);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [previewError, setPreviewError] = useState("");
  const [layerPreview, setLayerPreview] = useState(null);
  const [selectedLayers, setSelectedLayers] = useState([]);
  const [selectedDxfFile, setSelectedDxfFile] = useState(null);
  const [selectedDwgFile, setSelectedDwgFile] = useState(null);
  const [generatedScript, setGeneratedScript] = useState("");
  const [planList, setPlanList] = useState(() => {
    try {
      const raw = localStorage.getItem(PLAN_STORAGE_KEY);
      if (!raw) return DEFAULT_TEMPLATES;
      const list = JSON.parse(raw);
      return Array.isArray(list) && list.length > 0 ? list : DEFAULT_TEMPLATES;
    } catch {
      return DEFAULT_TEMPLATES;
    }
  });
  const [selectedPlanId, setSelectedPlanId] = useState("");
  const [planName, setPlanName] = useState("");

  const [walls, setWalls] = useState([]);
  const [rawPath, setRawPath] = useState([]);
  const [showWalls, setShowWalls] = useState(true);
  const [showPathPreview, setShowPathPreview] = useState(true);
  const [showGhostPath, setShowGhostPath] = useState(true);
  const [showCollisions, setShowCollisions] = useState(true);
  const [collisionCount, setCollisionCount] = useState(0);
  const [collisionsSample, setCollisionsSample] = useState([]);
  const [startPoint, setStartPoint] = useState([0, 0]);

  const [optimizeEnabled, setOptimizeEnabled] = useState(false);
  const [minSegmentLength, setMinSegmentLength] = useState(0.5);
  const [collinearAngleEpsDeg, setCollinearAngleEpsDeg] = useState(1.0);
  const [rdpEpsilon, setRdpEpsilon] = useState(0);
  const [generatedScriptRaw, setGeneratedScriptRaw] = useState("");
  const [generatedScriptOptimized, setGeneratedScriptOptimized] = useState("");
  const [scriptViewTab, setScriptViewTab] = useState("raw");

  const [planSource, setPlanSource] = useState("manual");
  const [advancedPlanOptionsOpen, setAdvancedPlanOptionsOpen] = useState(false);
  const [scriptPanelAdvancedOpen, setScriptPanelAdvancedOpen] = useState(false);
  const [drawMode, setDrawMode] = useState("basic");
  const [resultsStale, setResultsStale] = useState(false);
  const lastValidPlanInputsRef = useRef(null);

  function getPlanFingerprint() {
    const file = selectedDxfFile ?? selectedDwgFile;
    const fileKey = file
      ? `${file.name ?? ""}_${file.size ?? 0}_${file.lastModified ?? 0}`
      : null;
    return {
      planSource,
      stepSize,
      selectedLayers: [...(selectedLayers || [])].sort(),
      fileKey,
      planSpeed,
      worldScale,
      worldOffsetX,
      worldOffsetY
    };
  }

  useEffect(() => {
    if (result) {
      lastValidPlanInputsRef.current = getPlanFingerprint();
      setResultsStale(false);
    }
  }, [result]);

  useEffect(() => {
    if (!result || !lastValidPlanInputsRef.current) return;
    const fp = getPlanFingerprint();
    if (JSON.stringify(fp) === JSON.stringify(lastValidPlanInputsRef.current)) return;
    setResultsStale(true);
    setResult(null);
    setGeneratedScript("");
    setGeneratedScriptRaw("");
    setGeneratedScriptOptimized("");
    setScript("");
    lastValidPlanInputsRef.current = null;
    setTickState(null);
    setBlockedSim(null);
    setSimulateError("");
    setStep((s) => (s === "analyze" || s === "draw" ? "plan" : s));
    if (jobIdRef.current) {
      stopJob(jobIdRef.current).catch(() => {});
      jobIdRef.current = null;
    }
    if (simAbortRef.current) {
      simAbortRef.current.abort();
      simAbortRef.current = null;
    }
    queueRef.current = [];
    setSimRunning(false);
  }, [stepSize, selectedLayers, selectedDxfFile, selectedDwgFile, planSource, planSpeed, worldScale, worldOffsetX, worldOffsetY]);

  /** Backend import hata metnini kullanıcıya anlaşılır hale getirir (ağ / format / limit / boş plan). */
  function formatImportError(backendError, isNetworkError) {
    if (isNetworkError) return "Backend'e ulaşılamadı. Backend çalışıyor mu? (http://127.0.0.1:8000)";
    if (!backendError || typeof backendError !== "string") return "İçe aktarma hatası.";
    const e = backendError.toLowerCase();
    if (e.includes("entity") || e.includes("entities") || e.includes("binary") || e.includes("utf-8") || e.includes("ascii") || e.includes("dxf")) return "Dosya formatı veya içerik uygun değil. Sadece ASCII/UTF-8 DXF desteklenir. Detay: " + backendError;
    if (e.includes("çizilebilir") || e.includes("segment") || e.includes("nokta üretmedi") || e.includes("normalizasyon")) return "Plan çizilemiyor: " + backendError + " (step_size artırın veya daha az katman seçin)";
    if (e.includes("max_bounds_size") || e.includes("max_bounds")) return "Plan çizim alanı çok büyük. Öneri: Katman seçiminde 'recenter' açın veya daha az katman seçin. Detay: " + backendError;
    if (e.includes("max_moves") || e.includes("max_path") || e.includes("max_total_time")) return "Plan çok detaylı veya uzun. Öneri: step_size değerini artırın veya daha az katman seçin. Detay: " + backendError;
    return backendError;
  }

  function applyRecommendedStepSize() {
    if (!layerPreview || layerPreview.recommended_step_size == null) return;
    const value = Number(layerPreview.recommended_step_size);
    if (!Number.isFinite(value) || value <= 0) return;
    setStepSize(value);
  }

  /** step_size (m) için kullanıcı dostu etiket: Hızlı / Normal / Detay */
  function getStepAutoLabel(s) {
    if (s <= 0.1) return "Hızlı";
    if (s <= 0.25) return "Normal";
    return "Detay";
  }

  /** suggested_layers varsa onları, yoksa total_length'a göre en üst katman(lar)ı döner */
  function getEffectiveLayersForImport() {
    if (layerPreview?.suggested_layers?.length) return layerPreview.suggested_layers;
    if (layerPreview?.layers?.length) {
      const sorted = [...layerPreview.layers].sort((a, b) => {
        const la = Number(a.total_length ?? 0);
        const lb = Number(b.total_length ?? 0);
        return lb - la;
      });
      return sorted.slice(0, Math.min(2, sorted.length)).map((l) => l.name);
    }
    return selectedLayers?.length ? selectedLayers : [];
  }

  /** Sadece içe aktarır (analiz yok); komutları set eder ve Çizim adımına geçer. */
  async function runImportAndGenerateOnly(isDxf) {
    const file = isDxf ? selectedDxfFile : selectedDwgFile;
    if (!file) return null;
    setCompileError("");
    setImportWarnings([]);
    setImportBusy(true);
    try {
      const layersToUse = getEffectiveLayersForImport();
      const options = {
        normalize: true,
        return_plan_text: true,
        return_commands_text: true,
        return_raw_path: true,
        step_size: stepSize,
        speed: planSpeed,
        selected_layers: layersToUse?.length ? layersToUse : undefined
      };
      const importFn = isDxf ? importDxf : importDwg;
      const res = await importFn(file, options);
      if (res.ok === false) {
        setCompileError(formatImportError(res.error || (isDxf ? "DXF" : "DWG") + " içe aktarılamadı", false));
        setLastImport({ source: isDxf ? "dxf" : "dwg", fileName: file.name, when: new Date(), ok: false });
        return null;
      }
      if (res.warnings?.length) setImportWarnings(res.warnings);
      if (res.plan_text != null) setPlanText(res.plan_text);
      if (res.commands_text != null) {
        setGeneratedScript(res.commands_text);
        setGeneratedScriptRaw(res.commands_text);
        setGeneratedScriptOptimized(res.commands_text);
        setScript(res.commands_text);
      }
      if (res.walls != null) setWalls(res.walls);
      if (res.raw_path_points != null) setRawPath(Array.isArray(res.raw_path_points) ? res.raw_path_points : []);
      setLastImport({ source: isDxf ? "dxf" : "dwg", fileName: file.name, when: new Date(), ok: true });
      setStep("draw");
      return res;
    } catch (err) {
      const msg = String(err?.message || err);
      setCompileError(formatImportError(msg, msg === "Failed to fetch"));
      setLastImport({ source: isDxf ? "dxf" : "dwg", fileName: file.name, when: new Date(), ok: false });
      return null;
    } finally {
      setImportBusy(false);
    }
  }

  /** İçe aktar + analiz; sonucu Analiz adımında göster (retry için kullanılır). */
  async function runImportAndAnalyzeOnly(stepVal, layersToUse, isDxf) {
    const file = isDxf ? selectedDxfFile : selectedDwgFile;
    if (!file) return null;
    setCompileError("");
    setImportWarnings([]);
    setImportBusy(true);
    try {
      const options = {
        normalize: true,
        return_plan_text: true,
        return_commands_text: true,
        return_raw_path: true,
        step_size: stepVal,
        speed: planSpeed,
        selected_layers: layersToUse?.length ? layersToUse : undefined
      };
      const importFn = isDxf ? importDxf : importDwg;
      const res = await importFn(file, options);
      if (res.ok === false) {
        setCompileError(formatImportError(res.error || (isDxf ? "DXF" : "DWG") + " içe aktarılamadı", false));
        setLastImport({ source: isDxf ? "dxf" : "dwg", fileName: file.name, when: new Date(), ok: false });
        return null;
      }
      if (res.warnings?.length) setImportWarnings(res.warnings);
      if (res.plan_text != null) setPlanText(res.plan_text);
      if (res.commands_text != null) {
        setGeneratedScript(res.commands_text);
        setGeneratedScriptRaw(res.commands_text);
        setGeneratedScriptOptimized(res.commands_text);
        setScript(res.commands_text);
      }
      if (res.walls != null) setWalls(res.walls);
      if (res.raw_path_points != null) setRawPath(Array.isArray(res.raw_path_points) ? res.raw_path_points : []);
      setLastImport({ source: isDxf ? "dxf" : "dwg", fileName: file.name, when: new Date(), ok: true });
      const analyzeRes = await analyzeScenario(res.commands_text ?? script, startPoint, optimizePayload, res.walls ?? [], "warn");
      setResult(analyzeRes);
      const s = analyzeRes?.stats;
      setCollisionCount(s?.collision_count ?? 0);
      setCollisionsSample((s?.collisions_sample ?? []).slice(0, 50));
      return analyzeRes;
    } catch (err) {
      const msg = String(err?.message || err);
      setCompileError(formatImportError(msg, msg === "Failed to fetch"));
      setLastImport({ source: isDxf ? "dxf" : "dwg", fileName: file.name, when: new Date(), ok: false });
      return null;
    } finally {
      setImportBusy(false);
    }
  }

  function retryDxfCoarser() {
    const newStep = Math.min(stepSize * 2, 0.5);
    setStepSize(newStep);
    runImportAndAnalyzeOnly(newStep, selectedLayers, true);
  }
  function retryDxfWallsOnly() {
    const suggested = layerPreview?.suggested_layers;
    const wallLayers = (layerPreview?.layers || []).filter((l) => /wall|duvar/i.test(String(l.name))).map((l) => l.name);
    const layers = (suggested?.length ? suggested : wallLayers.length ? wallLayers : selectedLayers) || selectedLayers;
    setSelectedLayers(Array.isArray(layers) ? layers : []);
    runImportAndAnalyzeOnly(stepSize, Array.isArray(layers) ? layers : selectedLayers, true);
  }
  function retryDxfFiner() {
    const newStep = Math.max(stepSize * 0.75, 0.05);
    setStepSize(newStep);
    runImportAndAnalyzeOnly(newStep, selectedLayers, true);
  }
  function retryDwgCoarser() {
    const newStep = Math.min(stepSize * 2, 0.5);
    setStepSize(newStep);
    runImportAndAnalyzeOnly(newStep, selectedLayers, false);
  }
  function retryDwgWallsOnly() {
    const suggested = layerPreview?.suggested_layers;
    const wallLayers = (layerPreview?.layers || []).filter((l) => /wall|duvar/i.test(String(l.name))).map((l) => l.name);
    const layers = (suggested?.length ? suggested : wallLayers.length ? wallLayers : selectedLayers) || selectedLayers;
    setSelectedLayers(Array.isArray(layers) ? layers : []);
    runImportAndAnalyzeOnly(stepSize, Array.isArray(layers) ? layers : selectedLayers, false);
  }
  function retryDwgFiner() {
    const newStep = Math.max(stepSize * 0.75, 0.05);
    setStepSize(newStep);
    runImportAndAnalyzeOnly(newStep, selectedLayers, false);
  }

  function toggleLayerSelection(name) {
    setSelectedLayers((prev) =>
      prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name]
    );
  }

  function selectAllPreviewLayers() {
    if (!layerPreview || !Array.isArray(layerPreview.layers)) return;
    setSelectedLayers(layerPreview.layers.map((l) => l.name));
  }

  function clearPreviewLayers() {
    setSelectedLayers([]);
  }

  const [motionEnabled, setMotionEnabled] = useState(false);
  const [driftDegPerSec, setDriftDegPerSec] = useState(1.0);
  const [positionNoiseStd, setPositionNoiseStd] = useState(2.0);
  const [motionSeed, setMotionSeed] = useState("");

  const [debugViewMode, setDebugViewMode] = useState("simple");

  const [showExportModal, setShowExportModal] = useState(false);
  const [exportFormat, setExportFormat] = useState(() => {
    try {
      const saved = localStorage.getItem(EXPORT_FORMAT_STORAGE_KEY);
      if (saved === "robot_v1" || saved === "gcode_lite") return saved;
      if (saved === "flat") return "robot_v1";
    } catch (_) {}
    return "robot_v1";
  });
  const [exportContent, setExportContent] = useState("");
  const [exportFilename, setExportFilename] = useState("robot_export.robot_v1.txt");
  const [exportBlocked, setExportBlocked] = useState(false);
  const [exportBusy, setExportBusy] = useState(false);
  const [exportError, setExportError] = useState("");

  const optimizePayload = useMemo(() => optimizeEnabled ? {
    enabled: true,
    min_segment_length: minSegmentLength,
    collinear_angle_eps_deg: collinearAngleEpsDeg,
    rdp_epsilon: rdpEpsilon
  } : null, [optimizeEnabled, minSegmentLength, collinearAngleEpsDeg, rdpEpsilon]);

  const motionPayload = useMemo(() => {
    if (!motionEnabled) return { enabled: false };
    const seedNum = motionSeed.trim() === "" ? null : parseInt(motionSeed, 10);
    return {
      enabled: true,
      drift_deg_per_sec: driftDegPerSec,
      position_noise_std_per_sec: positionNoiseStd,
      ...(Number.isInteger(seedNum) ? { seed: seedNum } : {})
    };
  }, [motionEnabled, driftDegPerSec, positionNoiseStd, motionSeed]);

  const effectiveBounds = useMemo(() => {
    if (result?.stats?.bounds && result.stats.bounds.length === 4) return result.stats.bounds;
    const pts = [];
    walls.forEach(w => {
      if (w.length >= 4) { pts.push(w[0], w[1]); pts.push(w[2], w[3]); }
    });
    rawPath.forEach(p => { if (p.length >= 2) pts.push(p[0], p[1]); });
    if (pts.length < 2) return null;
    let minx = pts[0], maxx = pts[0], miny = pts[1], maxy = pts[1];
    for (let i = 0; i < pts.length; i += 2) {
      const x = pts[i], y = pts[i + 1];
      if (x < minx) minx = x; if (x > maxx) maxx = x;
      if (y < miny) miny = y; if (y > maxy) maxy = y;
    }
    return [minx, miny, maxx, maxy];
  }, [result?.stats?.bounds, walls, rawPath]);

  useEffect(() => {
    boundsRef.current = effectiveBounds;
  }, [effectiveBounds]);

  useEffect(() => {
    try {
      localStorage.setItem(PLAN_STORAGE_KEY, JSON.stringify(planList));
    } catch (_) {}
  }, [planList]);

  useEffect(() => {
    tickStateRef.current = tickState;
  }, [tickState]);

  const blocked = result?.blocked ?? false;
  const canGoToCizim = Boolean(generatedScript || script?.trim());
  const canGoToAnaliz = Boolean(result);

  const goToStep = useCallback((s) => {
    setStep(s);
  }, []);
  const parserErr = useMemo(() => (result?.parser || []).filter(d => d.severity === "ERROR").length, [result]);
  const parserWarn = useMemo(() => (result?.parser || []).filter(d => d.severity === "WARN").length, [result]);
  const analysisErr = useMemo(() => (result?.analysis || []).filter(d => d.severity === "ERROR").length, [result]);
  const analysisWarn = useMemo(() => (result?.analysis || []).filter(d => d.severity === "WARN").length, [result]);
  const analysisStatus = blocked ? "BLOCKED" : (analysisWarn > 0 || (result?.stats?.collision_count > 0)) ? "WARN" : "SAFE";

  const worldToScreen = useCallback((x, y) => {
    const v = viewRef.current;
    return {
      sx: x * v.scale + v.offsetX,
      sy: -y * v.scale + v.offsetY
    };
  }, []);

  const screenToWorld = useCallback((sx, sy) => {
    const v = viewRef.current;
    return {
      x: (sx - v.offsetX) / v.scale,
      y: -(sy - v.offsetY) / v.scale
    };
  }, []);

  const redrawCanvas = useCallback((lastTick) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const effectivePathPreview = drawMode === "developer" ? showPathPreview : false;
    const effectiveGhostPath = drawMode === "developer" ? showGhostPath : false;
    const ctx = canvas.getContext("2d");
    const w = canvas.width;
    const h = canvas.height;
    ctx.fillStyle = "#0b0b0b";
    ctx.fillRect(0, 0, w, h);
    if (showWalls && walls.length > 0) {
      ctx.strokeStyle = "#666";
      ctx.lineWidth = 1;
      ctx.beginPath();
      walls.forEach(seg => {
        if (seg.length >= 4) {
          const a = worldToScreen(seg[0], seg[1]);
          const b = worldToScreen(seg[2], seg[3]);
          ctx.moveTo(a.sx, a.sy);
          ctx.lineTo(b.sx, b.sy);
        }
      });
      ctx.stroke();
    }
    if (effectivePathPreview && rawPath.length > 1) {
      ctx.strokeStyle = "#3b82f6";
      ctx.lineWidth = 1;
      ctx.beginPath();
      const first = worldToScreen(rawPath[0][0], rawPath[0][1]);
      ctx.moveTo(first.sx, first.sy);
      for (let i = 1; i < rawPath.length; i++) {
        const p = worldToScreen(rawPath[i][0], rawPath[i][1]);
        ctx.lineTo(p.sx, p.sy);
      }
      ctx.stroke();
    }
    const ghostPoints = result?.stats?.path_points;
    if (effectiveGhostPath && ghostPoints && ghostPoints.length > 1) {
      ctx.strokeStyle = "rgba(148, 163, 184, 0.5)";
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      const first = worldToScreen(ghostPoints[0][0], ghostPoints[0][1]);
      ctx.moveTo(first.sx, first.sy);
      for (let i = 1; i < ghostPoints.length; i++) {
        const p = worldToScreen(ghostPoints[i][0], ghostPoints[i][1]);
        ctx.lineTo(p.sx, p.sy);
      }
      ctx.stroke();
      ctx.setLineDash([]);
    }
    const trace = traceRef.current;
    let prev = null;
    for (let i = 0; i < trace.length; i++) {
      const p = trace[i];
      const err = p.error ?? 0;
      const width = 1 + Math.min(6, err / 10);
      const alpha = Math.min(1, Math.max(0.2, 0.2 + err / 200));
      const { sx, sy } = worldToScreen(p.x, p.y);
      if (p.pen && prev) {
        ctx.strokeStyle = `rgba(74, 222, 128, ${alpha})`;
        ctx.lineWidth = width;
        ctx.beginPath();
        ctx.moveTo(prev.sx, prev.sy);
        ctx.lineTo(sx, sy);
        ctx.stroke();
      }
      prev = p.pen ? { sx, sy } : null;
    }
    if (lastTick) {
      const rx = lastTick.real_x ?? lastTick.x;
      const ry = lastTick.real_y ?? lastTick.y;
      const { sx, sy } = worldToScreen(rx, ry);
      ctx.fillStyle = lastTick.pen ? "#22c55e" : "#64748b";
      ctx.beginPath();
      ctx.arc(sx, sy, 4, 0, Math.PI * 2);
      ctx.fill();
    }
    if (startPoint && startPoint.length >= 2) {
      const { sx, sy } = worldToScreen(startPoint[0], startPoint[1]);
      ctx.strokeStyle = "#22c55e";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(sx, sy, 6, 0, Math.PI * 2);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(sx - 5, sy);
      ctx.lineTo(sx + 5, sy);
      ctx.moveTo(sx, sy - 5);
      ctx.lineTo(sx, sy + 5);
      ctx.stroke();
    }

    if (showCollisions && collisionsSample.length > 0) {
      ctx.save();
      ctx.strokeStyle = "#ef4444";
      ctx.fillStyle = "#ef4444";
      collisionsSample.forEach((c) => {
        if (c.x == null || c.y == null) return;
        const { sx, sy } = worldToScreen(c.x, c.y);
        ctx.beginPath();
        ctx.arc(sx, sy, 4, 0, Math.PI * 2);
        ctx.fill();
      });
      ctx.restore();
    }
  }, [worldToScreen, showWalls, showPathPreview, showGhostPath, showCollisions, walls, rawPath, startPoint, result?.stats?.path_points, collisionsSample, drawMode]);

  const flushOneAndDraw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let lastPayload = null;
    while (queueRef.current.length > 0) {
      const payload = queueRef.current.shift();
      traceRef.current.push({
        x: payload.real_x ?? payload.x,
        y: payload.real_y ?? payload.y,
        idealX: payload.ideal_x,
        idealY: payload.ideal_y,
        error: payload.error ?? 0,
        pen: payload.pen,
        drew: payload.drew
      });
      setTickState(payload);
      lastPayload = payload;
    }
    redrawCanvas(lastPayload || tickStateRef.current);
  }, [redrawCanvas]);

  const rafLoop = useCallback(() => {
    if (queueRef.current.length > 0) flushOneAndDraw();
    rafIdRef.current = requestAnimationFrame(rafLoop);
  }, [flushOneAndDraw]);

  useEffect(() => {
    if (step === "draw" && canvasRef.current) {
      const w = canvasRef.current.width;
      const h = canvasRef.current.height;
      viewRef.current = computeFitView(boundsRef.current, w, h, MARGIN);
      redrawCanvas(tickStateRef.current);
    }
  }, [step, redrawCanvas]);

  const handleClearCanvas = useCallback(() => {
    if (rafIdRef.current != null) {
      cancelAnimationFrame(rafIdRef.current);
      rafIdRef.current = null;
    }
    queueRef.current = [];
    traceRef.current = [];
    setTickState(null);
    setBlockedSim(null);
    setSimulateError("");
    if (canvasRef.current) {
      viewRef.current = computeFitView(boundsRef.current, canvasRef.current.width, canvasRef.current.height, MARGIN);
    }
    redrawCanvas(null);
  }, [redrawCanvas]);

  const handleFitView = useCallback(() => {
    if (canvasRef.current) {
      viewRef.current = computeFitView(boundsRef.current, canvasRef.current.width, canvasRef.current.height, MARGIN);
      redrawCanvas(tickStateRef.current);
    }
  }, [redrawCanvas]);

  const handleResetView = useCallback(() => {
    if (canvasRef.current) {
      const w = canvasRef.current.width;
      const h = canvasRef.current.height;
      viewRef.current = resetView(w, h);
      redrawCanvas(tickStateRef.current);
    }
  }, [redrawCanvas]);

  async function onStartSimulate() {
    setSimulateError("");
    setBlockedSim(null);
    if (rafIdRef.current != null) cancelAnimationFrame(rafIdRef.current);
    queueRef.current = [];
    rafIdRef.current = requestAnimationFrame(rafLoop);
    const ac = new AbortController();
    simAbortRef.current = ac;
    setSimRunning(true);
    traceRef.current = [];
    setTickState(null);
    if (canvasRef.current) {
      viewRef.current = computeFitView(boundsRef.current, canvasRef.current.width, canvasRef.current.height, MARGIN);
    }
    const onEvent = (eventName, payload) => {
      if (eventName === "tick") queueRef.current.push(payload);
      else if (eventName === "done") {
        setTickState(prev => (prev ? { ...prev, ...payload, finished: true } : { ...payload, finished: true }));
        setSimRunning(false);
        if (rafIdRef.current != null) {
          cancelAnimationFrame(rafIdRef.current);
          rafIdRef.current = null;
        }
      } else if (eventName === "error") {
        setSimulateError(payload.message || "Simülasyon hatası");
        setSimRunning(false);
        if (rafIdRef.current != null) {
          cancelAnimationFrame(rafIdRef.current);
          rafIdRef.current = null;
        }
      }
    };
    try {
      const out = await createJob(script, { dt: 0.016, speed_multiplier: speedMultiplier, start: startPoint, optimize: optimizePayload, motion: motionPayload, walls, collisionMode: "warn" });
      if (!out.ok) {
        setBlockedSim(out);
        setSimRunning(false);
        if (rafIdRef.current != null) {
          cancelAnimationFrame(rafIdRef.current);
          rafIdRef.current = null;
        }
        return;
      }
      jobIdRef.current = out.job_id;
      await getJobStream(out.job_id, onEvent, ac.signal);
      jobIdRef.current = null;
      setSimRunning(false);
      if (rafIdRef.current != null) {
        cancelAnimationFrame(rafIdRef.current);
        rafIdRef.current = null;
      }
    } catch (e) {
      jobIdRef.current = null;
      if (e?.name === "AbortError") {
        setSimRunning(false);
        if (rafIdRef.current != null) {
          cancelAnimationFrame(rafIdRef.current);
          rafIdRef.current = null;
        }
        return;
      }
      setSimulateError(String(e?.message || e));
      setSimRunning(false);
      if (rafIdRef.current != null) {
        cancelAnimationFrame(rafIdRef.current);
        rafIdRef.current = null;
      }
    }
  }

  async function onStopSimulate() {
    if (jobIdRef.current) {
      await stopJob(jobIdRef.current);
      jobIdRef.current = null;
    }
    if (simAbortRef.current) {
      simAbortRef.current.abort();
      simAbortRef.current = null;
    }
    if (rafIdRef.current != null) {
      cancelAnimationFrame(rafIdRef.current);
      rafIdRef.current = null;
    }
    queueRef.current = [];
  }

  async function onAnalyze() {
    setErr("");
    setBusy(true);
    try {
      const res = await analyzeScenario(script, startPoint, optimizePayload, walls, "warn");
      setResult(res);
      const s = res?.stats;
      setCollisionCount(s?.collision_count ?? 0);
      setCollisionsSample((s?.collisions_sample ?? []).slice(0, 50));
    } catch (e) {
      setErr(String(e?.message || e));
    } finally {
      setBusy(false);
    }
  }

  /** Manuel plan: script varsa analiz et ve Analiz adımına geç */
  async function runAnalyzeOnlyAndGoToAnalyze() {
    if (!script?.trim()) return;
    setErr("");
    setBusy(true);
    try {
      const res = await analyzeScenario(script, startPoint, optimizePayload, walls, "warn");
      setResult(res);
      const s = res?.stats;
      setCollisionCount(s?.collision_count ?? 0);
      setCollisionsSample((s?.collisions_sample ?? []).slice(0, 50));
      setStep("analyze");
    } catch (e) {
      setErr(String(e?.message || e));
    } finally {
      setBusy(false);
    }
  }

  function onSavePlan() {
    const name = (planName || "Unnamed").trim();
    const options = { step_size: stepSize, speed: planSpeed, world_scale: worldScale, world_offset: [worldOffsetX, worldOffsetY] };
    if (selectedPlanId) {
      setPlanList(prev => prev.map(p => p.id === selectedPlanId ? { ...p, name, plan_text: planText, options, updated_at: new Date().toISOString() } : p));
    } else {
      const id = `plan-${Date.now()}`;
      setPlanList(prev => [...prev, { id, name, plan_text: planText, options, updated_at: new Date().toISOString() }]);
      setSelectedPlanId(id);
    }
  }

  function onLoadPlan(id) {
    setSelectedPlanId(id);
    const p = planList.find(x => x.id === id);
    if (!p) return;
    setPlanName(p.name ?? "");
    setPlanText(p.plan_text ?? "");
    setStepSize(p.options?.step_size ?? 5);
    setPlanSpeed(p.options?.speed ?? 120);
    setWorldScale(p.options?.world_scale ?? 1);
    setWorldOffsetX(Array.isArray(p.options?.world_offset) ? p.options.world_offset[0] : 0);
    setWorldOffsetY(Array.isArray(p.options?.world_offset) ? p.options.world_offset[1] : 0);
  }

  function onDeletePlan() {
    if (!selectedPlanId) return;
    setPlanList(prev => prev.filter(p => p.id !== selectedPlanId));
    setSelectedPlanId("");
  }

  async function onGenerateScript() {
    setCompileError("");
    setCompileBusy(true);
    setGeneratedScript("");
    setGeneratedScriptRaw("");
    setGeneratedScriptOptimized("");
    try {
      const res = await compilePlan(planText, {
        step_size: stepSize,
        speed: planSpeed,
        world_scale: worldScale,
        world_offset: [worldOffsetX, worldOffsetY],
        optimize: optimizePayload
      });
      if (!res.ok) {
        setCompileError(res.error || "Plan derlenemedi");
        return;
      }
      const raw = res.commands_text_raw ?? res.commands_text ?? "";
      const opt = res.commands_text_optimized ?? raw;
      setGeneratedScriptRaw(raw);
      setGeneratedScriptOptimized(opt);
      setGeneratedScript(raw);
      setScript(raw);
      setWalls(res.walls ?? []);
      setRawPath(res.raw_path_points ?? []);
      setStep("draw");
    } catch (e) {
      const msg = String(e?.message || e);
      setCompileError(msg === "Failed to fetch" ? "Backend'e ulaşılamadı. Backend çalışıyor mu? (http://127.0.0.1:8000)" : msg);
    } finally {
      setCompileBusy(false);
    }
  }

  async function onImportJson(payload, fileName = null) {
    setCompileError("");
    setImportWarnings([]);
    setImportSuccessMessage("");
    setImportBusy(true);
    try {
      const res = await importPlanFromJson({
        ...payload,
        normalize: true,
        return_plan_text: true,
        return_commands_text: true,
        return_raw_path: true,
        step_size: stepSize,
        speed: planSpeed
      });
      if (res.ok === false) {
        const msg = res.error || "JSON içe aktarılamadı";
        setCompileError(formatImportError(msg, false));
        if (fileName) {
          setLastImport({ source: "json", fileName, when: new Date(), ok: false });
        }
        return;
      }
      if (res.warnings?.length) setImportWarnings(res.warnings);
      if (res.plan_text != null) setPlanText(res.plan_text);
      if (res.commands_text != null) {
        setGeneratedScript(res.commands_text);
        setGeneratedScriptRaw(res.commands_text);
        setGeneratedScriptOptimized(res.commands_text);
        setScript(res.commands_text);
      }
      if (res.walls != null) setWalls(res.walls);
      if (res.raw_path_points != null) setRawPath(Array.isArray(res.raw_path_points) ? res.raw_path_points : []);
      setImportSuccessMessage("JSON içe aktarıldı.");
      setTimeout(() => setImportSuccessMessage(""), 4000);
      if (fileName) {
        setLastImport({ source: "json", fileName, when: new Date(), ok: true });
      }
      setStep("draw");
    } catch (e) {
      const msg = String(e?.message || e);
      setCompileError(formatImportError(msg, msg === "Failed to fetch"));
      if (fileName) {
        setLastImport({ source: "json", fileName, when: new Date(), ok: false });
      }
    } finally {
      setImportBusy(false);
    }
  }

  function onJsonFileSelect(e) {
    const file = e?.target?.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const json = JSON.parse(reader.result);
        onImportJson(json, file.name);
      } catch {
        setCompileError("Dosya geçerli JSON değil.");
      }
      e.target.value = "";
    };
    reader.readAsText(file);
  }

  function onLoadSampleJson() {
    const sample = {
      room: { width: 400, height: 300 },
      obstacles: [],
      start: { x: 50, y: 50 },
      waypoints: [
        { x: 350, y: 50 },
        { x: 350, y: 250 },
        { x: 50, y: 250 },
        { x: 50, y: 50 }
      ]
    };
    onImportJson(sample, "Örnek JSON");
  }

  async function onDxfFileSelect(e) {
    const file = e?.target?.files?.[0];
    if (!file) return;
    setCompileError("");
    setImportWarnings([]);
    setImportSuccessMessage("");
    setPreviewError("");
    setLayerPreview(null);
    setSelectedLayers([]);
    setSelectedDxfFile(file);
    setPreviewBusy(true);
    try {
      const previewRes = await importDxf(file, {
        preview_layers: true
      });
      if (previewRes.ok === false) {
        const msg = previewRes.error || "DXF önizleme başarısız";
        setPreviewError(formatImportError(msg, false));
      } else {
        const layers = previewRes.layers || [];
        const suggested = previewRes.suggested_layers || [];
        setLayerPreview({
          source: "dxf",
          fileName: file.name,
          layers,
          suggested_layers: suggested,
          recommended_step_size: previewRes.recommended_step_size ?? null
        });
        let defaults = [];
        if (suggested.length) {
          defaults = suggested;
        } else if (layers.length) {
          const sorted = [...layers].sort((a, b) => {
            const la = Number(a.total_length ?? 0);
            const lb = Number(b.total_length ?? 0);
            if (lb !== la) return lb - la;
            return String(a.name).localeCompare(String(b.name));
          });
          defaults = sorted.slice(0, Math.min(2, sorted.length)).map((l) => l.name);
        }
        setSelectedLayers(defaults);
        const rec = previewRes.recommended_step_size;
        const stepAuto = rec != null && Number.isFinite(Number(rec))
          ? Math.max(0.05, Math.min(0.5, Number(rec)))
          : 0.15;
        setStepSize(stepAuto);
      }
    } catch (err) {
      const msg = String(err?.message || err);
      setPreviewError(formatImportError(msg, msg === "Failed to fetch"));
    } finally {
      setPreviewBusy(false);
    }
    e.target.value = "";
  }

  async function runDxfImportWithLayers() {
    if (!selectedDxfFile) return;
    setCompileError("");
    setImportWarnings([]);
    setImportBusy(true);
    try {
      const options = {
        normalize: true,
        return_plan_text: true,
        return_commands_text: true,
        return_raw_path: true,
        step_size: stepSize,
        speed: planSpeed,
        selected_layers: selectedLayers.length ? selectedLayers : undefined
      };
      const res = await importDxf(selectedDxfFile, options);
      if (res.ok === false) {
        setCompileError(formatImportError(res.error || "DXF içe aktarılamadı", false));
        setLastImport({ source: "dxf", fileName: selectedDxfFile.name, when: new Date(), ok: false });
        return;
      }
      if (res.warnings?.length) setImportWarnings(res.warnings);
      if (res.plan_text != null) setPlanText(res.plan_text);
      if (res.commands_text != null) {
        setGeneratedScript(res.commands_text);
        setGeneratedScriptRaw(res.commands_text);
        setGeneratedScriptOptimized(res.commands_text);
        setScript(res.commands_text);
      }
      if (res.walls != null) setWalls(res.walls);
      if (res.raw_path_points != null) setRawPath(Array.isArray(res.raw_path_points) ? res.raw_path_points : []);
      setImportSuccessMessage("DXF içe aktarıldı.");
      setTimeout(() => setImportSuccessMessage(""), 4000);
      setLastImport({ source: "dxf", fileName: selectedDxfFile.name, when: new Date(), ok: true });
    } catch (err) {
      const msg = String(err?.message || err);
      setCompileError(formatImportError(msg, msg === "Failed to fetch"));
      setLastImport({ source: "dxf", fileName: selectedDxfFile.name, when: new Date(), ok: false });
    } finally {
      setImportBusy(false);
    }
  }

  async function runDxfImportQuick() {
    if (!selectedDxfFile) return;
    setCompileError("");
    setImportWarnings([]);
    setImportBusy(true);
    try {
      const options = {
        normalize: true,
        return_plan_text: true,
        return_commands_text: true,
        return_raw_path: true,
        step_size: stepSize,
        speed: planSpeed
      };
      const res = await importDxf(selectedDxfFile, options);
      if (res.ok === false) {
        setCompileError(formatImportError(res.error || "DXF içe aktarılamadı", false));
        setLastImport({ source: "dxf", fileName: selectedDxfFile.name, when: new Date(), ok: false });
        return;
      }
      if (res.warnings?.length) setImportWarnings(res.warnings);
      if (res.plan_text != null) setPlanText(res.plan_text);
      if (res.commands_text != null) {
        setGeneratedScript(res.commands_text);
        setGeneratedScriptRaw(res.commands_text);
        setGeneratedScriptOptimized(res.commands_text);
        setScript(res.commands_text);
      }
      if (res.walls != null) setWalls(res.walls);
      if (res.raw_path_points != null) setRawPath(Array.isArray(res.raw_path_points) ? res.raw_path_points : []);
      setImportSuccessMessage("DXF içe aktarıldı.");
      setTimeout(() => setImportSuccessMessage(""), 4000);
      setLastImport({ source: "dxf", fileName: selectedDxfFile.name, when: new Date(), ok: true });
    } catch (err) {
      const msg = String(err?.message || err);
      setCompileError(formatImportError(msg, msg === "Failed to fetch"));
      setLastImport({ source: "dxf", fileName: selectedDxfFile.name, when: new Date(), ok: false });
    } finally {
      setImportBusy(false);
    }
  }

  async function onDwgFileSelect(e) {
    const file = e?.target?.files?.[0];
    if (!file) return;
    setCompileError("");
    setImportWarnings([]);
    setImportSuccessMessage("");
    setPreviewError("");
    setLayerPreview(null);
    setSelectedLayers([]);
    setSelectedDwgFile(file);
    setPreviewBusy(true);
    try {
      const previewRes = await importDwg(file, {
        preview_layers: true
      });
      if (previewRes.ok === false) {
        const msg = previewRes.error || "DWG önizleme başarısız";
        setPreviewError(formatImportError(msg, false));
      } else {
        const layers = previewRes.layers || [];
        const suggested = previewRes.suggested_layers || [];
        setLayerPreview({
          source: "dwg",
          fileName: file.name,
          layers,
          suggested_layers: suggested,
          recommended_step_size: previewRes.recommended_step_size ?? null
        });
        let defaults = [];
        if (suggested.length) {
          defaults = suggested;
        } else if (layers.length) {
          const sorted = [...layers].sort((a, b) => {
            const la = Number(a.total_length ?? 0);
            const lb = Number(b.total_length ?? 0);
            if (lb !== la) return lb - la;
            return String(a.name).localeCompare(String(b.name));
          });
          defaults = sorted.slice(0, Math.min(2, sorted.length)).map((l) => l.name);
        }
        setSelectedLayers(defaults);
        const rec = previewRes.recommended_step_size;
        const stepAuto = rec != null && Number.isFinite(Number(rec))
          ? Math.max(0.05, Math.min(0.5, Number(rec)))
          : 0.15;
        setStepSize(stepAuto);
      }
    } catch (err) {
      const msg = String(err?.message || err);
      setPreviewError(formatImportError(msg, msg === "Failed to fetch"));
    } finally {
      setPreviewBusy(false);
    }
    e.target.value = "";
  }

  async function runDwgImportWithLayers() {
    if (!selectedDwgFile) return;
    setCompileError("");
    setImportWarnings([]);
    setImportBusy(true);
    try {
      const options = {
        normalize: true,
        return_plan_text: true,
        return_commands_text: true,
        return_raw_path: true,
        step_size: stepSize,
        speed: planSpeed,
        selected_layers: selectedLayers.length ? selectedLayers : undefined
      };
      const res = await importDwg(selectedDwgFile, options);
      if (res.ok === false) {
        setCompileError(formatImportError(res.error || "DWG içe aktarılamadı", false));
        setLastImport({ source: "dwg", fileName: selectedDwgFile.name, when: new Date(), ok: false });
        return;
      }
      if (res.warnings?.length) setImportWarnings(res.warnings);
      if (res.plan_text != null) setPlanText(res.plan_text);
      if (res.commands_text != null) {
        setGeneratedScript(res.commands_text);
        setGeneratedScriptRaw(res.commands_text);
        setGeneratedScriptOptimized(res.commands_text);
        setScript(res.commands_text);
      }
      if (res.walls != null) setWalls(res.walls);
      if (res.raw_path_points != null) setRawPath(Array.isArray(res.raw_path_points) ? res.raw_path_points : []);
      setImportSuccessMessage("DWG içe aktarıldı.");
      setTimeout(() => setImportSuccessMessage(""), 4000);
      setLastImport({ source: "dwg", fileName: selectedDwgFile.name, when: new Date(), ok: true });
    } catch (err) {
      const msg = String(err?.message || err);
      setCompileError(formatImportError(msg, msg === "Failed to fetch"));
      setLastImport({ source: "dwg", fileName: selectedDwgFile.name, when: new Date(), ok: false });
    } finally {
      setImportBusy(false);
    }
  }

  async function runDwgImportQuick() {
    if (!selectedDwgFile) return;
    setCompileError("");
    setImportWarnings([]);
    setImportBusy(true);
    try {
      const options = {
        normalize: true,
        return_plan_text: true,
        return_commands_text: true,
        return_raw_path: true,
        step_size: stepSize,
        speed: planSpeed
      };
      const res = await importDwg(selectedDwgFile, options);
      if (res.ok === false) {
        setCompileError(formatImportError(res.error || "DWG içe aktarılamadı", false));
        setLastImport({ source: "dwg", fileName: selectedDwgFile.name, when: new Date(), ok: false });
        return;
      }
      if (res.warnings?.length) setImportWarnings(res.warnings);
      if (res.plan_text != null) setPlanText(res.plan_text);
      if (res.commands_text != null) {
        setGeneratedScript(res.commands_text);
        setGeneratedScriptRaw(res.commands_text);
        setGeneratedScriptOptimized(res.commands_text);
        setScript(res.commands_text);
      }
      if (res.walls != null) setWalls(res.walls);
      if (res.raw_path_points != null) setRawPath(Array.isArray(res.raw_path_points) ? res.raw_path_points : []);
      setImportSuccessMessage("DWG içe aktarıldı.");
      setTimeout(() => setImportSuccessMessage(""), 4000);
      setLastImport({ source: "dwg", fileName: selectedDwgFile.name, when: new Date(), ok: true });
    } catch (err) {
      const msg = String(err?.message || err);
      setCompileError(formatImportError(msg, msg === "Failed to fetch"));
      setLastImport({ source: "dwg", fileName: selectedDwgFile.name, when: new Date(), ok: false });
    } finally {
      setImportBusy(false);
    }
  }

  function onSelectScriptTab(tab) {
    setScriptViewTab(tab);
    if (tab === "raw") setScript(generatedScriptRaw || script);
    else setScript(generatedScriptOptimized || script);
  }

  function handleLoadExample() {
    setScript(DEFAULT_SCRIPT);
    setResult(null);
    setErr("");
  }

  function handleClearScript() {
    setScript("");
    setResult(null);
    setErr("");
  }

  const editorArea = (
    <div style={{ border: "1px solid #333", borderRadius: 12, padding: 12, boxShadow: "0 10px 24px rgba(0,0,0,0.4)" }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8, marginBottom: 8 }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 2 }}>Komut editörü</div>
          <div style={{ fontSize: 12, opacity: 0.75 }}>SPEED, PEN, MOVE, TURN, FORWARD, REPEAT… desteklenir</div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            type="button"
            onClick={handleLoadExample}
            style={{
              padding: "6px 10px",
              borderRadius: 8,
              border: "1px solid #444",
              background: "#1d3b7a",
              color: "#fff",
              fontSize: 12,
              cursor: "pointer",
              fontWeight: 600
            }}
          >
            Örnek yükle
          </button>
          <button
            type="button"
            onClick={handleClearScript}
            style={{
              padding: "6px 10px",
              borderRadius: 8,
              border: "1px solid #444",
              background: "#333",
              color: "#eee",
              fontSize: 12,
              cursor: "pointer",
              fontWeight: 600
            }}
          >
            Temizle
          </button>
        </div>
      </div>
      <textarea
        value={script}
        onChange={(e) => setScript(e.target.value)}
        spellCheck={false}
        style={{
          width: "100%",
          height: step === "draw" ? 320 : 520,
          marginTop: 4,
          borderRadius: 10,
          border: "1px solid #333",
          background: "#0b0b0b",
          color: "#eee",
          padding: 12,
          fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
          fontSize: 13,
          lineHeight: 1.35
        }}
      />
    </div>
  );

  return (
    <div style={{ minHeight: "100vh", background: "#111", color: "#eee", padding: 18, fontFamily: "system-ui" }}>
      <h2 style={{ margin: 0 }}>PlanDraw</h2>
      <StepperNav step={step} onGoToStep={goToStep} canGoToCizim={canGoToCizim} canGoToAnaliz={canGoToAnaliz} />
      <StatusBanner
        planName={lastImport?.ok ? lastImport.fileName : null}
        stepLabel={layerPreview?.recommended_step_size != null ? getStepAutoLabel(stepSize) : null}
        stepValue={stepSize}
        layersCount={selectedLayers?.length}
        resultsStale={resultsStale}
      />

      {step === "analyze" && (
        <div style={{ maxWidth: 560, marginTop: 16 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div
              style={{
                border: "1px solid #333",
                borderRadius: 12,
                padding: 14,
                background: "#151515",
                boxShadow: "0 10px 25px rgba(0,0,0,0.45)"
              }}
            >
              <div style={{ fontWeight: 800, marginBottom: 10, fontSize: 15 }}>Durum</div>
              {result ? (
                <>
                  <StatusPillLarge status={analysisStatus} />
                  <div style={{ marginTop: 12 }}>
                    <MetricsGrid stats={result?.stats} collisionCount={collisionCount} showDebugCounts={false} />
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 12 }}>
                    <div style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #333", background: parserErr === 0 ? "#0f2e1a" : "#3b0a0a", color: parserErr === 0 ? "#86efac" : "#fca5a5", fontSize: 13 }}>
                      Parser: {parserErr === 0 ? "✅ Hata yok" : `❌ ${parserErr} hata`}
                    </div>
                    <div style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #333", background: analysisErr === 0 && collisionCount === 0 ? "#0f2e1a" : "#3b0a0a", color: analysisErr === 0 && collisionCount === 0 ? "#86efac" : "#fca5a5", fontSize: 13 }}>
                      Analiz: {analysisErr === 0 && collisionCount === 0 ? "✅ Çakışma yok" : `⚠ Çakışma: ${collisionCount}`}
                    </div>
                    <div style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #333", background: "#111", color: "#94a3b8", fontSize: 13 }}>
                      ⏱ Tahmini süre: {formatSecondsShort(result?.stats?.estimated_time)}
                    </div>
                  </div>
                </>
              ) : (
                <div style={{ fontSize: 13, opacity: 0.7 }}>Önce senaryoyu analiz edin.</div>
              )}
            </div>

            {blocked && result && (lastImport?.source === "dxf" || lastImport?.source === "dwg") && (
              <div style={{ border: "1px solid #444", borderRadius: 12, padding: 14, background: "#1a1a1a" }}>
                <div style={{ fontWeight: 700, marginBottom: 10, fontSize: 14 }}>Alternatif modlar</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
                  <button
                    type="button"
                    onClick={lastImport?.source === "dxf" ? retryDxfCoarser : retryDwgCoarser}
                    disabled={importBusy}
                    style={{ padding: "10px 16px", borderRadius: 8, border: "1px solid #555", background: "#2d2d2d", color: "#eee", fontWeight: 600, cursor: importBusy ? "not-allowed" : "pointer" }}
                  >
                    Hızlı mod (daha kaba)
                  </button>
                  <button
                    type="button"
                    onClick={lastImport?.source === "dxf" ? retryDxfWallsOnly : retryDwgWallsOnly}
                    disabled={importBusy}
                    style={{ padding: "10px 16px", borderRadius: 8, border: "1px solid #555", background: "#2d2d2d", color: "#eee", fontWeight: 600, cursor: importBusy ? "not-allowed" : "pointer" }}
                  >
                    Sadece duvarlar
                  </button>
                  <button
                    type="button"
                    onClick={lastImport?.source === "dxf" ? retryDxfFiner : retryDwgFiner}
                    disabled={importBusy}
                    style={{ padding: "10px 16px", borderRadius: 8, border: "1px solid #555", background: "#2d2d2d", color: "#eee", fontWeight: 600, cursor: importBusy ? "not-allowed" : "pointer" }}
                  >
                    Detay mod
                  </button>
                </div>
              </div>
            )}

            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <button
                type="button"
                onClick={() => goToStep("draw")}
                style={{ padding: "10px 20px", borderRadius: 8, border: "none", background: "#1d3b7a", color: "#fff", fontWeight: 700, cursor: "pointer" }}
              >
                Çizime dön
              </button>
              <button
                type="button"
                onClick={() => goToStep("plan")}
                style={{ padding: "10px 20px", borderRadius: 8, border: "1px solid #444", background: "#333", color: "#fff", fontWeight: 700, cursor: "pointer" }}
              >
                Yeniden oluştur
              </button>
            </div>

            <div
              style={{
                border: "1px solid #333",
                borderRadius: 12,
                padding: 14,
                background: "#151515",
                boxShadow: "0 10px 25px rgba(0,0,0,0.45)"
              }}
            >
              <div style={{ fontWeight: 800, marginBottom: 8, fontSize: 15 }}>Hızlı özet</div>
              {result?.stats ? (
                <div style={{ fontSize: 13, lineHeight: 1.6 }}>
                  <div>
                    🧭 Çizim alanı: <b>{formatBoundsHuman(result.stats.bounds)}</b>
                  </div>
                  <div>
                    ⏱ Yaklaşık süre: <b>{formatSecondsShort(result.stats.estimated_time)}</b>
                  </div>
                  <div>
                    📏 Toplam çizgi uzunluğu: <b>{formatNumberCompact(result.stats.path_length, 1)} unit</b>
                  </div>
                  <div>
                    🔁 Hareket sayısı: <b>{result.stats.move_count ?? "—"}</b>
                  </div>
                  <div>
                    🧱 Çakışma sayısı: <b>{collisionCount}</b>
                  </div>
                  {result.stats.original_move_count != null && result.stats.optimized_move_count != null && (
                    <div style={{ marginTop: 4 }}>
                      ✨ Optimizasyon:{" "}
                      <b>
                        {result.stats.reduction_ratio != null
                          ? `${Number(result.stats.reduction_ratio).toFixed(1)}% azaldı`
                          : "aktif"}
                      </b>{" "}
                      ({result.stats.original_move_count} → {result.stats.optimized_move_count})
                    </div>
                  )}
                </div>
              ) : (
                <div style={{ fontSize: 13, opacity: 0.7 }}>Çizim adımında &quot;Analiz et&quot; ile başlatın.</div>
              )}
            </div>

            <Accordion
              title="Geliştirici detayları"
              subtitle={`Parser: ${parserErr} err / ${parserWarn} warn · Analysis: ${analysisErr} err / ${analysisWarn} warn`}
              defaultOpen={false}
            >
              {(!result || ((result.parser || []).length === 0 && (result.analysis || []).length === 0)) ? (
                <div style={{ opacity: 0.85 }}>Her şey temiz ✅</div>
              ) : (
                <>
                  <div style={{ marginBottom: 8 }}>
                    <div style={{ fontWeight: 700, fontSize: 12, color: "#fca5a5", marginBottom: 4 }}>Parser</div>
                    {(result.parser || []).filter((d) => d.severity === "ERROR").map((d, idx) => (
                      <div key={`perr-${idx}`} style={{ marginBottom: 6, padding: 6, borderRadius: 6, background: "#3b0a0a" }}>
                        <div style={{ fontWeight: 600, fontSize: 12 }}>❌ Satır {d.line}</div>
                        <div style={{ fontSize: 12 }}>{d.message}</div>
                        {d.text ? (
                          <div style={{ marginTop: 4, fontFamily: "monospace", fontSize: 11, opacity: 0.85 }}>{d.text}</div>
                        ) : null}
                      </div>
                    ))}
                    {(result.parser || []).filter((d) => d.severity === "WARN").map((d, idx) => (
                      <div key={`pwarn-${idx}`} style={{ marginBottom: 6, padding: 6, borderRadius: 6, background: "#3f2e00" }}>
                        <div style={{ fontWeight: 600, fontSize: 12 }}>⚠ Satır {d.line}</div>
                        <div style={{ fontSize: 12 }}>{d.message}</div>
                        {d.text ? (
                          <div style={{ marginTop: 4, fontFamily: "monospace", fontSize: 11, opacity: 0.85 }}>{d.text}</div>
                        ) : null}
                      </div>
                    ))}
                    {(result.parser || []).length === 0 && <div style={{ opacity: 0.8 }}>Parser tarafında sorun yok.</div>}
                  </div>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: 12, color: "#fca5a5", marginBottom: 4 }}>Analysis</div>
                    {(result.analysis || []).filter((d) => d.severity === "ERROR").map((d, idx) => (
                      <div key={`aerr-${idx}`} style={{ marginBottom: 6, padding: 6, borderRadius: 6, background: "#3b0a0a" }}>
                        <div style={{ fontWeight: 600, fontSize: 12 }}>❌ Satır {d.line}</div>
                        <div style={{ fontSize: 12 }}>{d.message}</div>
                        {d.text ? (
                          <div style={{ marginTop: 4, fontFamily: "monospace", fontSize: 11, opacity: 0.85 }}>{d.text}</div>
                        ) : null}
                      </div>
                    ))}
                    {(result.analysis || []).filter((d) => d.severity === "WARN").map((d, idx) => (
                      <div key={`awarn-${idx}`} style={{ marginBottom: 6, padding: 6, borderRadius: 6, background: "#3f2e00" }}>
                        <div style={{ fontWeight: 600, fontSize: 12 }}>⚠ Satır {d.line}</div>
                        <div style={{ fontSize: 12 }}>{d.message}</div>
                        {d.text ? (
                          <div style={{ marginTop: 4, fontFamily: "monospace", fontSize: 11, opacity: 0.85 }}>{d.text}</div>
                        ) : null}
                      </div>
                    ))}
                    {(result.analysis || []).length === 0 && <div style={{ opacity: 0.8 }}>Analysis tarafında sorun yok.</div>}
                  </div>
                </>
              )}
            </Accordion>

            <Accordion title="Geliştirici detayları" subtitle="Unrolled komutlar ve ham istatistikler" defaultOpen={false}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                <div style={{ fontWeight: 600, fontSize: 12 }}>Ham veriler</div>
                <button
                  type="button"
                  onClick={() => {
                    const parts = [];
                    if (result?.commands_unrolled) parts.push(result.commands_unrolled);
                    if (result?.stats) parts.push(JSON.stringify(result.stats, null, 2));
                    const text = parts.join("\n\n--- stats ---\n\n");
                    if (text && navigator.clipboard?.writeText) {
                      navigator.clipboard.writeText(text);
                    }
                  }}
                  style={{
                    padding: "4px 8px",
                    borderRadius: 6,
                    border: "1px solid #444",
                    background: "#222",
                    color: "#eee",
                    fontSize: 11,
                    cursor: "pointer"
                  }}
                >
                  Kopyala
                </button>
              </div>
              <div style={{ fontSize: 11, opacity: 0.8, marginBottom: 6 }}>İçerik yalnızca görüntü amaçlıdır; backend çıktısı değiştirilmez.</div>
              <div style={{ marginBottom: 8 }}>
                <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 4 }}>Stats (JSON)</div>
                <pre
                  style={{
                    maxHeight: 140,
                    overflow: "auto",
                    border: "1px solid #333",
                    borderRadius: 8,
                    padding: 8,
                    background: "#0b0b0b",
                    fontSize: 11
                  }}
                >
                  {result?.stats ? JSON.stringify(result.stats, null, 2) : "{}"}
                </pre>
              </div>
              <div>
                <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 4 }}>Unrolled commands</div>
                <textarea
                  readOnly
                  value={result?.commands_unrolled || ""}
                  style={{
                    width: "100%",
                    maxHeight: 160,
                    borderRadius: 8,
                    border: "1px solid #333",
                    background: "#0b0b0b",
                    color: "#eee",
                    padding: 8,
                    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                    fontSize: 11,
                    lineHeight: 1.35,
                    resize: "vertical"
                  }}
                />
              </div>
            </Accordion>
          </div>
        </div>
      )}

      {step === "draw" && (
        <>
          {blockedSim && (
            <div style={{ marginTop: 12, padding: 12, background: "#3d1010", border: "1px solid #a33", borderRadius: 10 }}>
              <div style={{ fontWeight: 800, marginBottom: 8 }}>BLOCKED — Simülasyon başlatılamadı</div>
              <DiagList title="Parser" items={blockedSim.parser_diags || []} />
              <DiagList title="Analysis" items={blockedSim.analysis_diags || []} />
            </div>
          )}
          {simulateError && (
            <div style={{ marginTop: 12, color: "#ff7070" }}>{simulateError}</div>
          )}
          <div style={{ display: "grid", gridTemplateColumns: "380px 1fr", gap: 14, marginTop: 14, alignItems: "start" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
                <button
                  onClick={onStartSimulate}
                  disabled={simRunning || busy}
                  style={{ padding: "8px 14px", borderRadius: 8, border: "none", background: simRunning || busy ? "#333" : "#166534", color: "#fff", cursor: simRunning || busy ? "not-allowed" : "pointer", fontWeight: 600 }}
                >
                  {simRunning ? "Çiziliyor…" : "Çiz"}
                </button>
                <button
                  onClick={runAnalyzeOnlyAndGoToAnalyze}
                  disabled={busy || !(script?.trim())}
                  style={{ padding: "8px 14px", borderRadius: 8, border: "1px solid #444", background: busy ? "#222" : "#1d3b7a", color: "#fff", cursor: busy || !(script?.trim()) ? "not-allowed" : "pointer", fontWeight: 600 }}
                >
                  {busy ? "Analiz ediliyor…" : "Analiz et"}
                </button>
                <button
                  onClick={onStopSimulate}
                  disabled={!simRunning}
                  style={{ padding: "8px 14px", borderRadius: 8, border: "1px solid #444", background: !simRunning ? "#222" : "#991b1b", color: "#fff", cursor: !simRunning ? "not-allowed" : "pointer", fontWeight: 600 }}
                >
                  Durdur
                </button>
                <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
                  <span>Hız:</span>
                  <input
                    type="range"
                    min={0.2}
                    max={3}
                    step={0.1}
                    value={speedMultiplier}
                    onChange={(e) => setSpeedMultiplier(Number(e.target.value))}
                    disabled={simRunning}
                    style={{ width: 80 }}
                  />
                  <span style={{ minWidth: 32 }}>{speedMultiplier.toFixed(1)}x</span>
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, cursor: "pointer" }}>
                  <input type="checkbox" checked={showWalls} onChange={(e) => setShowWalls(e.target.checked)} />
                  Duvarlar
                </label>
                <button
                  onClick={handleClearCanvas}
                  style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #444", background: "#333", color: "#fff", cursor: "pointer", fontWeight: 600 }}
                >
                  Temizle
                </button>
                <button
                  onClick={() => { setShowExportModal(true); setExportContent(""); setExportError(""); setExportBlocked(false); }}
                  style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #444", background: "#333", color: "#fff", cursor: "pointer", fontWeight: 600 }}
                >
                  Export
                </button>
                <select
                  value={exportFormat}
                  onChange={(e) => {
                    const v = e.target.value;
                    setExportFormat(v);
                    try {
                      localStorage.setItem(EXPORT_FORMAT_STORAGE_KEY, v);
                    } catch (_) {}
                  }}
                  style={{ padding: "6px 8px", background: "#222", color: "#eee", border: "1px solid #444", borderRadius: 6, fontSize: 12 }}
                  title="Export formatı"
                >
                  <option value="robot_v1">Robot V1</option>
                  <option value="gcode_lite">Gcode Lite</option>
                </select>
              </div>
              {(simRunning || tickState) && (
                <div style={{ padding: "8px 12px", border: "1px solid #333", borderRadius: 8, background: "#151515", fontSize: 12, display: "flex", flexWrap: "wrap", gap: 12, alignItems: "center" }}>
                  <span>
                    İlerleme: <strong>{tickState?.finished ? 100 : (result?.stats?.move_count && Number.isFinite(tickState?.idx) ? Math.min(100, Math.round((tickState.idx / result.stats.move_count) * 100)) : 0)}%</strong>
                  </span>
                  {result?.stats?.estimated_time != null && tickState?.t != null && !tickState.finished && (
                    <span>
                      Kalan: <strong>{Math.max(0, ((result.stats.estimated_time - tickState.t) / speedMultiplier)).toFixed(1)} s</strong>
                    </span>
                  )}
                  <span>
                    Kalem: <strong style={{ color: tickState?.pen ? "#22c55e" : "#94a3b8" }}>{tickState?.pen ? "DOWN" : "UP"}</strong>
                  </span>
                </div>
              )}
              <div style={{ border: "1px solid #333", borderRadius: 12, padding: 10, background: "#151515" }}>
                <div style={{ fontWeight: 700, marginBottom: 6, fontSize: 13 }}>Komut önizlemesi</div>
                <pre
                  readOnly
                  style={{
                    maxHeight: 200,
                    overflow: "auto",
                    margin: 0,
                    padding: 8,
                    borderRadius: 8,
                    border: "1px solid #333",
                    background: "#0b0b0b",
                    color: "#eee",
                    fontSize: 11,
                    lineHeight: 1.35,
                    fontFamily: "ui-monospace, monospace",
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-all"
                  }}
                >
                  {script || "(Komut yok)"}
                </pre>
                <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                  <button
                    type="button"
                    onClick={() => script && navigator.clipboard?.writeText(script)}
                    style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #444", background: "#222", color: "#eee", fontSize: 12, cursor: "pointer" }}
                  >
                    Kopyala
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      if (!script) return;
                      const blob = new Blob([script], { type: "text/plain" });
                      const a = document.createElement("a");
                      a.href = URL.createObjectURL(blob);
                      a.download = "commands.txt";
                      a.click();
                      URL.revokeObjectURL(a.href);
                    }}
                    style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #444", background: "#222", color: "#eee", fontSize: 12, cursor: "pointer" }}
                  >
                    İndir
                  </button>
                </div>
              </div>
              <Accordion title="Komut düzenleyici" subtitle="Scripti elle düzenle" defaultOpen={false}>
                {editorArea}
              </Accordion>
              <Accordion title="Gelişmiş çizim" subtitle="Görünüm ve hata simülasyonu" defaultOpen={false}>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                    <button type="button" onClick={() => setDrawMode("basic")} style={{ padding: "6px 10px", borderRadius: 8, border: "1px solid #444", background: drawMode === "basic" ? "#1d3b7a" : "#222", color: "#fff", cursor: "pointer", fontSize: 12 }}>Basit</button>
                    <button type="button" onClick={() => setDrawMode("developer")} style={{ padding: "6px 10px", borderRadius: 8, border: "1px solid #444", background: drawMode === "developer" ? "#1d3b7a" : "#222", color: "#fff", cursor: "pointer", fontSize: 12 }}>Geliştirici</button>
                  </div>
                  {drawMode === "developer" && (
                    <>
                      <button onClick={onAnalyze} disabled={busy} style={{ padding: "6px 10px", borderRadius: 8, border: "1px solid #444", background: busy ? "#222" : "#1d3b7a", color: "#fff", cursor: busy ? "not-allowed" : "pointer", fontSize: 12 }}>{busy ? "Analiz ediliyor…" : "Analiz et"}</button>
                      <div style={{ display: "flex", gap: 4 }}>
                        <button onClick={handleFitView} style={{ padding: "6px 10px", borderRadius: 8, border: "1px solid #444", background: "#333", color: "#fff", cursor: "pointer", fontSize: 12 }}>Fit</button>
                        <button onClick={handleResetView} style={{ padding: "6px 10px", borderRadius: 8, border: "1px solid #444", background: "#333", color: "#fff", cursor: "pointer", fontSize: 12 }}>Reset</button>
                      </div>
                      <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, cursor: "pointer" }}>
                        <input type="checkbox" checked={showPathPreview} onChange={(e) => setShowPathPreview(e.target.checked)} />
                        Path preview
                      </label>
                      <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, cursor: "pointer" }}>
                        <input type="checkbox" checked={showGhostPath} onChange={(e) => setShowGhostPath(e.target.checked)} />
                        Ghost path
                      </label>
                      <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, cursor: "pointer" }}>
                        <input type="checkbox" checked={motionEnabled} onChange={(e) => setMotionEnabled(e.target.checked)} disabled={simRunning} />
                        Motion error
                      </label>
                      {motionEnabled && (
                        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", fontSize: 11 }}>
                          <label>Drift °/s <input type="number" min={0} step={0.5} value={driftDegPerSec} onChange={(e) => setDriftDegPerSec(Number(e.target.value))} disabled={simRunning} style={{ width: 48, padding: 4, background: "#222", color: "#eee", border: "1px solid #444" }} /></label>
                          <label>Noise <input type="number" min={0} step={0.5} value={positionNoiseStd} onChange={(e) => setPositionNoiseStd(Number(e.target.value))} disabled={simRunning} style={{ width: 48, padding: 4, background: "#222", color: "#eee", border: "1px solid #444" }} /></label>
                          <label>Seed <input type="text" placeholder="opsiyonel" value={motionSeed} onChange={(e) => setMotionSeed(e.target.value)} disabled={simRunning} style={{ width: 56, padding: 4, background: "#222", color: "#eee", border: "1px solid #444" }} /></label>
                        </div>
                      )}
                    </>
                  )}
                </div>
              </Accordion>
            </div>
            <div
              style={{ border: "1px solid #333", borderRadius: 12, padding: 12 }}
              onWheel={(e) => e.preventDefault()}
              role="presentation"
            >
              <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 8 }}>
                <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, cursor: "pointer" }}>
                  <input type="checkbox" checked={showWalls} onChange={(e) => setShowWalls(e.target.checked)} />
                  Duvarları göster
                </label>
                {drawMode === "developer" && (
                  <>
                    <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, cursor: "pointer" }}>
                      <input type="checkbox" checked={showPathPreview} onChange={(e) => setShowPathPreview(e.target.checked)} />
                      Show path preview
                    </label>
                    <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, cursor: "pointer" }}>
                      <input type="checkbox" checked={showGhostPath} onChange={(e) => setShowGhostPath(e.target.checked)} />
                      Show ghost path
                    </label>
                  </>
                )}
              </div>
              <canvas
                ref={canvasRef}
                width={600}
                height={400}
                style={{ width: "100%", maxWidth: 600, height: 400, background: "#0b0b0b", borderRadius: 8, display: "block", cursor: "crosshair" }}
                onClick={(e) => {
                  if (skippedClickRef.current) {
                    skippedClickRef.current = false;
                    return;
                  }
                  const canvas = canvasRef.current;
                  if (!canvas || simRunning) return;
                  const rect = canvas.getBoundingClientRect();
                  const sx = (e.clientX - rect.left) * (canvas.width / rect.width);
                  const sy = (e.clientY - rect.top) * (canvas.height / rect.height);
                  const { x, y } = screenToWorld(sx, sy);
                  setStartPoint([x, y]);
                  redrawCanvas(tickStateRef.current);
                }}
                onMouseDown={(e) => {
                  const canvas = canvasRef.current;
                  if (!canvas) return;
                  const rect = canvas.getBoundingClientRect();
                  const sx = (e.clientX - rect.left) * (canvas.width / rect.width);
                  const sy = (e.clientY - rect.top) * (canvas.height / rect.height);
                  panStartRef.current = { sx, sy, offsetX: viewRef.current.offsetX, offsetY: viewRef.current.offsetY, moved: false };
                }}
                onMouseMove={(e) => {
                  if (!panStartRef.current) return;
                  const canvas = canvasRef.current;
                  if (!canvas) return;
                  const rect = canvas.getBoundingClientRect();
                  const sx = (e.clientX - rect.left) * (canvas.width / rect.width);
                  const sy = (e.clientY - rect.top) * (canvas.height / rect.height);
                  const dx = sx - panStartRef.current.sx;
                  const dy = sy - panStartRef.current.sy;
                  panStartRef.current.moved = true;
                  viewRef.current = {
                    ...viewRef.current,
                    offsetX: panStartRef.current.offsetX + dx,
                    offsetY: panStartRef.current.offsetY + dy
                  };
                  redrawCanvas(tickStateRef.current);
                }}
                onMouseLeave={() => { panStartRef.current = null; }}
                onMouseUp={() => {
                  if (panStartRef.current) {
                    skippedClickRef.current = panStartRef.current.moved;
                    panStartRef.current = null;
                  }
                }}
                onWheel={(e) => {
                  e.preventDefault();
                  const canvas = canvasRef.current;
                  if (!canvas) return;
                  const rect = canvas.getBoundingClientRect();
                  const sx = (e.clientX - rect.left) * (canvas.width / rect.width);
                  const sy = (e.clientY - rect.top) * (canvas.height / rect.height);
                  const zoomFactor = Math.exp(-e.deltaY * 0.001);
                  const v = viewRef.current;
                  const newScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, v.scale * zoomFactor));
                  const pivot = screenToWorld(sx, sy);
                  viewRef.current = {
                    scale: newScale,
                    offsetX: sx - pivot.x * newScale,
                    offsetY: sy + pivot.y * newScale
                  };
                  redrawCanvas(tickStateRef.current);
                }}
              />
              <div style={{ marginTop: 10, fontSize: 12, fontFamily: "monospace", lineHeight: 1.5 }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
                  <div style={{ fontWeight: 600 }}>Canlı izleme</div>
                  <div style={{ display: "flex", gap: 6 }}>
                    <button
                      type="button"
                      onClick={() => setDebugViewMode("simple")}
                      style={{
                        padding: "2px 8px",
                        borderRadius: 999,
                        border: "1px solid #444",
                        background: debugViewMode === "simple" ? "#1d3b7a" : "#111",
                        color: "#eee",
                        fontSize: 11,
                        cursor: "pointer"
                      }}
                    >
                      Basit
                    </button>
                    <button
                      type="button"
                      onClick={() => setDebugViewMode("dev")}
                      style={{
                        padding: "2px 8px",
                        borderRadius: 999,
                        border: "1px solid #444",
                        background: debugViewMode === "dev" ? "#1d3b7a" : "#111",
                        color: "#eee",
                        fontSize: 11,
                        cursor: "pointer"
                      }}
                    >
                      Geliştirici
                    </button>
                  </div>
                </div>
                {tickState ? (
                  debugViewMode === "simple" ? (
                    <>
                      <div>
                        Konum: x={Number(tickState.real_x ?? tickState.x).toFixed(2)}, y=
                        {Number(tickState.real_y ?? tickState.y).toFixed(2)}
                      </div>
                      {motionEnabled && (tickState.error != null || tickState.error_mean != null || tickState.error_max != null) && (
                        <div>
                          Hata (anlık/ortalama/maks):{" "}
                          {Number(tickState.error ?? 0).toFixed(3)} / {Number(tickState.error_mean ?? 0).toFixed(3)} /{" "}
                          {Number(tickState.error_max ?? 0).toFixed(3)}
                        </div>
                      )}
                      <div>
                        Durum:{" "}
                        {tickState.finished
                          ? "Bitti"
                          : tickState.wait > 0
                          ? "Bekliyor"
                          : simRunning
                          ? "Çiziyor"
                          : "Hazır"}
                      </div>
                      {collisionCount > 0 && (
                        <div>Collisions: {collisionCount}</div>
                      )}
                    </>
                  ) : (
                    <>
                      <div>idx: {tickState.idx}</div>
                      <div>wait: {Number(tickState.wait ?? 0).toFixed(3)}</div>
                      <div>heading_deg: {Number(tickState.heading_deg ?? 0).toFixed(2)}</div>
                      <div>target: {tickState.target != null ? String(tickState.target) : "—"}</div>
                      <div>finished: {tickState.finished ? "true" : "false"}</div>
                      {collisionsSample.slice(0, 10).map((c, idx) => (
                        <div key={`col-${idx}`} style={{ fontSize: 11 }}>
                          {c.kind} @{" "}
                          {c.x != null && c.y != null ? `${c.x.toFixed(2)}, ${c.y.toFixed(2)}` : "None"} (wall={c.wall_index ?? "?"}, seg={c.seg_index ?? "?"})
                        </div>
                      ))}
                    </>
                  )
                ) : (
                  <div style={{ opacity: 0.7 }}>Canlı debug — simülasyon başlayınca güncellenir</div>
                )}
              </div>
            </div>
          </div>
        </>
      )}

      {showExportModal && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }} onClick={() => setShowExportModal(false)}>
          <div style={{ background: "#222", border: "1px solid #444", borderRadius: 12, padding: 20, maxWidth: 560, width: "90%", maxHeight: "85vh", overflow: "auto" }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
              <h3 style={{ margin: 0 }}>Robot Export (W6)</h3>
              <button type="button" onClick={() => setShowExportModal(false)} style={{ background: "transparent", border: "none", color: "#aaa", cursor: "pointer", fontSize: 18 }}>×</button>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
              <span style={{ fontSize: 13 }}>Format:</span>
              <select
                value={exportFormat}
                onChange={(e) => {
                  const v = e.target.value;
                  setExportFormat(v);
                  try {
                    localStorage.setItem(EXPORT_FORMAT_STORAGE_KEY, v);
                  } catch (_) {}
                }}
                style={{ padding: "6px 10px", background: "#111", color: "#eee", border: "1px solid #444", borderRadius: 6 }}
              >
                <option value="robot_v1">Robot V1</option>
                <option value="gcode_lite">Gcode Lite</option>
              </select>
              <button
                disabled={exportBusy}
                onClick={async () => {
                  setExportBusy(true);
                  setExportError("");
                  try {
                    const res = await exportRobot(script, { start: startPoint, format: exportFormat, optimize: optimizePayload });
                    setExportContent(res.content ?? "");
                    setExportFilename(res.filename ?? "robot_export.txt");
                    setExportBlocked(res.blocked ?? false);
                  } catch (e) {
                    setExportError(String(e?.message ?? e));
                    setExportContent("");
                  } finally {
                    setExportBusy(false);
                  }
                }}
                style={{ padding: "8px 14px", borderRadius: 8, border: "1px solid #444", background: exportBusy ? "#333" : "#1d3b7a", color: "#fff", cursor: exportBusy ? "not-allowed" : "pointer", fontWeight: 600 }}
              >
                {exportBusy ? "Oluşturuluyor…" : "Oluştur"}
              </button>
            </div>
            <Accordion title="Geliştirici" subtitle="Backend format bilgisi" defaultOpen={false}>
              <div style={{ fontSize: 12, color: "#94a3b8", lineHeight: 1.5 }}>
                Backend yalnızca <strong style={{ color: "#e2e8f0" }}>robot_v1</strong> ve <strong style={{ color: "#e2e8f0" }}>gcode_lite</strong> formatlarını destekler. &quot;Flat&quot; etiketi kullanılmıyor; aynı çıktı Robot V1 seçeneği ile üretilir.
              </div>
            </Accordion>
            {exportError && <div style={{ color: "#ff7070", fontSize: 13, marginBottom: 8 }}>{exportError}</div>}
            {exportBlocked && exportContent && (
              <div style={{ padding: 10, background: "#3d1010", border: "1px solid #a33", borderRadius: 8, marginBottom: 10, fontSize: 13 }}>
                BLOCKED — Export dosyası üretildi ama çalıştırma önerilmez.
              </div>
            )}
            {exportContent && (
              <>
                <div style={{ fontSize: 12, marginBottom: 6, opacity: 0.9 }}>Önizleme (ilk ~40 satır):</div>
                <textarea
                  readOnly
                  value={exportContent.split("\n").slice(0, 40).join("\n")}
                  style={{ width: "100%", height: 180, resize: "none", background: "#0b0b0b", color: "#eee", border: "1px solid #444", borderRadius: 8, padding: 10, fontFamily: "monospace", fontSize: 12 }}
                />
                <div style={{ marginTop: 10 }}>
                  <button
                    onClick={() => {
                      const blob = new Blob([exportContent], { type: "text/plain" });
                      const a = document.createElement("a");
                      a.href = URL.createObjectURL(blob);
                      a.download = exportFilename;
                      a.click();
                      URL.revokeObjectURL(a.href);
                    }}
                    style={{ padding: "8px 14px", borderRadius: 8, border: "1px solid #444", background: "#166534", color: "#fff", cursor: "pointer", fontWeight: 600 }}
                  >
                    İndir
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {step === "plan" && (
        <div style={{ maxWidth: 640, marginTop: 14 }}>
          <div style={{ border: "1px solid #333", borderRadius: 12, padding: 12 }}>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 10, marginBottom: 10 }}>
              <input
                type="text"
                placeholder="Plan adı"
                value={planName}
                onChange={(e) => setPlanName(e.target.value)}
                style={{ width: 140, padding: "6px 8px", background: "#222", color: "#eee", border: "1px solid #444", borderRadius: 6 }}
              />
              <select
                value={selectedPlanId}
                onChange={(e) => onLoadPlan(e.target.value)}
                style={{ padding: "6px 10px", background: "#222", color: "#eee", border: "1px solid #444", borderRadius: 6, minWidth: 160 }}
              >
                <option value="">— Plan seç —</option>
                {planList.map(p => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
              <button onClick={onSavePlan} style={{ padding: "6px 12px", borderRadius: 6, border: "1px solid #444", background: "#1d3b7a", color: "#fff", cursor: "pointer" }}>Kaydet</button>
              <button onClick={onDeletePlan} disabled={!selectedPlanId} style={{ padding: "6px 12px", borderRadius: 6, border: "1px solid #444", background: selectedPlanId ? "#991b1b" : "#333", color: "#fff", cursor: selectedPlanId ? "pointer" : "not-allowed" }}>Sil</button>
            </div>
            <PlanSourceSelector selectedSource={planSource} onChange={setPlanSource} />
            {layerPreview && (layerPreview.source === "dxf" || layerPreview.source === "dwg") && (
              <div style={{ marginBottom: 12, padding: 10, border: "1px solid #333", borderRadius: 8, background: "#151515", fontSize: 12 }}>
                <div style={{ fontWeight: 700, marginBottom: 6 }}>Önizleme özeti</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
                  <span>Adım: <b>{getStepAutoLabel(stepSize)}</b> ({Number(stepSize).toFixed(2)} m)</span>
                  <span>Toplam uzunluk: <b>{(() => {
                    const layers = layerPreview.layers || [];
                    const sel = selectedLayers?.length ? selectedLayers : layers.slice(0, 2).map(l => l.name);
                    const total = layers.filter(l => sel.includes(l.name)).reduce((s, l) => s + Number(l.total_length ?? 0), 0);
                    return total.toFixed(1);
                  })()} m</b></span>
                  <span>Katman: <b>{selectedLayers?.length ?? 0}</b></span>
                </div>
              </div>
            )}
            {planSource === "dxf" && (
              <DxfImportPanel
                importBusy={importBusy}
                onFileSelect={onDxfFileSelect}
                warnings={importWarnings}
                lastImport={lastImport}
                previewBusy={previewBusy && layerPreview && layerPreview.source === "dxf"}
                previewError={previewError}
                layerPreview={layerPreview}
                selectedLayers={selectedLayers}
                onToggleLayer={toggleLayerSelection}
                onSelectAllLayers={selectAllPreviewLayers}
                onClearLayers={clearPreviewLayers}
                selectedFile={selectedDxfFile}
                stepSize={stepSize}
                getStepAutoLabel={getStepAutoLabel}
                onGenerateCommands={() => runImportAndGenerateOnly(true)}
              />
            )}
            {planSource === "dwg" && (
              <DwgImportPanel
                importBusy={importBusy}
                onFileSelect={onDwgFileSelect}
                warnings={importWarnings}
                lastImport={lastImport}
                previewBusy={previewBusy && layerPreview && layerPreview.source === "dwg"}
                previewError={previewError}
                layerPreview={layerPreview}
                selectedLayers={selectedLayers}
                onToggleLayer={toggleLayerSelection}
                onSelectAllLayers={selectAllPreviewLayers}
                onClearLayers={clearPreviewLayers}
                selectedFile={selectedDwgFile}
                stepSize={stepSize}
                getStepAutoLabel={getStepAutoLabel}
                onGenerateCommands={() => runImportAndGenerateOnly(false)}
              />
            )}
            {planSource === "json" && (
              <JsonImportPanel importBusy={importBusy} onFileSelect={onJsonFileSelect} onLoadSample={onLoadSampleJson} warnings={importWarnings} lastImport={lastImport} />
            )}
            {planSource === "manual" && (
              <LinePlanEditor planText={planText} onChange={setPlanText} onGenerateScript={onGenerateScript} compileBusy={compileBusy} importBusy={importBusy} compileError={compileError} />
            )}
            {compileError && (planSource === "dxf" || planSource === "dwg" || planSource === "json") && (
              <div style={{ marginTop: 10, color: "#ff7070", fontSize: 13 }}>{compileError}</div>
            )}
            {importSuccessMessage && (
              <div style={{ marginTop: 10, color: "#22c55e", fontSize: 13 }}>{importSuccessMessage}</div>
            )}
            <AdvancedOptionsPanel open={advancedPlanOptionsOpen} onToggle={() => setAdvancedPlanOptionsOpen(v => !v)} stepSize={stepSize} setStepSize={setStepSize} planSpeed={planSpeed} setPlanSpeed={setPlanSpeed} worldScale={worldScale} setWorldScale={setWorldScale} worldOffsetX={worldOffsetX} setWorldOffsetX={setWorldOffsetX} worldOffsetY={worldOffsetY} setWorldOffsetY={setWorldOffsetY} />
          </div>
        </div>
      )}

    </div>
  );
}
