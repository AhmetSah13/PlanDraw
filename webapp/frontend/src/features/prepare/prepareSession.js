import { SESSION_KEYS } from "../../shared/sessionKeys.js";

/**
 * Sonraki fazlar (Plan / Execute) için oturum köprüsü — isteğe bağlı okuma.
 */
export function savePrepareSnapshot(payload) {
  try {
    sessionStorage.setItem(SESSION_KEYS.PREPARE_SNAPSHOT, JSON.stringify(payload));
  } catch (_) {}
}

export function loadPrepareSnapshot() {
  try {
    const raw = sessionStorage.getItem(SESSION_KEYS.PREPARE_SNAPSHOT);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

/**
 * Plan ekranı çıktısı (yeniden derleme / doğrulama sonrası Execute için).
 */
export function savePlanSnapshot(payload) {
  try {
    sessionStorage.setItem(SESSION_KEYS.PLAN_SNAPSHOT, JSON.stringify(payload));
  } catch (_) {}
}

export function loadPlanSnapshot() {
  try {
    const raw = sessionStorage.getItem(SESSION_KEYS.PLAN_SNAPSHOT);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

/** Son tamamlanan / kayıtlı job özeti (Monitor veya tekrar bağlanma için). */
export function saveExecuteLastRun(payload) {
  try {
    sessionStorage.setItem(SESSION_KEYS.EXECUTE_LAST_RUN, JSON.stringify(payload));
  } catch (_) {}
}

export function loadExecuteLastRun() {
  try {
    const raw = sessionStorage.getItem(SESSION_KEYS.EXECUTE_LAST_RUN);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

/**
 * Execute için bağlam: önce Plan anlığı, yoksa Prepare anlığı (Plan ekranı ile aynı öncelik).
 */
export function loadExecutionSnapshot() {
  const plan = loadPlanSnapshot();
  if (plan && plan.commandsText?.trim()) return { ...plan, _source: "plan" };
  const prep = loadPrepareSnapshot();
  if (prep && prep.commandsText?.trim()) return { ...prep, _source: "prepare" };
  return null;
}

/**
 * Execute ekranından periyodik yazılır; Monitor salt-okunur gözlem için okur.
 */
export function saveMonitorSession(payload) {
  try {
    sessionStorage.setItem(SESSION_KEYS.MONITOR_SESSION, JSON.stringify(payload));
  } catch (_) {}
}

export function loadMonitorSession() {
  try {
    const raw = sessionStorage.getItem(SESSION_KEYS.MONITOR_SESSION);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

/** Align ekranı: kontrol noktaları, tolerans, son hizalama raporu (Plan/Execute ile paylaşılabilir). */
export function saveAlignSnapshot(payload) {
  try {
    sessionStorage.setItem(SESSION_KEYS.ALIGN_SNAPSHOT, JSON.stringify(payload));
  } catch (_) {}
}

export function loadAlignSnapshot() {
  try {
    const raw = sessionStorage.getItem(SESSION_KEYS.ALIGN_SNAPSHOT);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}
