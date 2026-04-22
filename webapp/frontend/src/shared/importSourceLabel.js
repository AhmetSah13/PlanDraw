/**
 * lastImport.source için kısa gösterim etiketi (Plan / Execute / Monitor ortak).
 */
export function importSourceLabel(lastImport) {
  if (!lastImport) return "—";
  const s = lastImport.source;
  if (s === "dxf") return "DXF";
  if (s === "dwg") return "DWG";
  if (s === "json") return "JSON";
  if (s === "manual") return "Manuel LINE";
  return String(s || "—");
}
