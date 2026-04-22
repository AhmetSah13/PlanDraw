import { loadAlignSnapshot } from "../../features/prepare/prepareSession.js";

/**
 * Align oturum anlığından gate ve özet (Plan / Execute / flow ortak).
 * @param {object|null} [snapshot] — verilmezse loadAlignSnapshot() okunur
 */
export function readAlignContext(snapshot) {
  const raw = snapshot !== undefined ? snapshot : loadAlignSnapshot();
  const a = raw?.lastAlignment ?? null;
  const hasRun = Boolean(a && (a.point_count != null || a.transform_type));
  const blocked = a?.blocked === true;
  const allowed = hasRun && !blocked;

  let gate = "none";
  if (!hasRun) gate = "none";
  else if (blocked) gate = "blocked";
  else gate = "allowed";

  return {
    raw,
    alignment: a,
    hasRun,
    blocked,
    allowed,
    gate,
    updatedAt: raw?.updatedAt ?? null,
  };
}
