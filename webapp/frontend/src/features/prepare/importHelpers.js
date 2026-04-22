/**
 * İçe aktarma uyarıları ve adım etiketi — legacy App ile aynı mantık (saf fonksiyon).
 */

export const DEFAULT_PLAN = `# square room
LINE 0 0 200 0
LINE 200 0 200 200
LINE 200 200 0 200
LINE 0 200 0 0
`;

export function getStepAutoLabel(s) {
  if (s <= 0.1) return "Hızlı";
  if (s <= 0.25) return "Normal";
  return "Detay";
}

export function formatImportWarningItem(item) {
  if (typeof item === "string") return item;
  if (!item || typeof item !== "object") return String(item);
  const code = item.code ? `[${String(item.code)}] ` : "";
  const message = item.message ? String(item.message) : JSON.stringify(item);
  const action = item.user_action ? ` (Öneri: ${String(item.user_action)})` : "";
  return `${code}${message}${action}`;
}

export function collectImportWarnings(res) {
  const merged = [];
  if (Array.isArray(res?.warnings)) merged.push(...res.warnings);
  if (Array.isArray(res?.parse_warnings)) merged.push(...res.parse_warnings);
  if (Array.isArray(res?.warning_codes) && res.warning_codes.length > 0) {
    merged.push(`Uyarı kodları: ${res.warning_codes.join(", ")}`);
  }
  const normalized = merged
    .map((w) => formatImportWarningItem(w))
    .map((w) => String(w).trim())
    .filter(Boolean);
  return Array.from(new Set(normalized));
}
