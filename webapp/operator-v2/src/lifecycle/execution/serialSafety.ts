import type {
  HizalamaDurumu,
  KontrolDurumu,
  PlanHazirligi,
} from "../../workflow/store/workflowStore";

export type LiveSerialGateReason =
  | "plan-yok"
  | "hizalama-yok"
  | "hizalama-riskli"
  | "kontrol-yok"
  | "kontrol-blocked"
  | "kontrol-bulgusu"
  | "carpisma-riski"
  | "onay-yok"
  | "hazir";

export interface LiveSerialGateInput {
  planHazirligi: PlanHazirligi | null;
  hizalamaDurumu: HizalamaDurumu | null;
  kontrolDurumu: KontrolDurumu | null;
  canliOnay: boolean;
}

export interface LiveSerialGateResult {
  allowed: boolean;
  reason: LiveSerialGateReason;
}

function hasDiagnostics(kontrolDurumu: KontrolDurumu) {
  return Boolean(kontrolDurumu.yanit.parser.length || kontrolDurumu.yanit.analysis.length);
}

function hasCollisionRisk(kontrolDurumu: KontrolDurumu) {
  const stats = kontrolDurumu.yanit.stats;
  return Boolean(
    (stats.collision_count ?? 0) > 0 ||
      (stats.wall_proper_cross_count ?? 0) > 0,
  );
}

export function getLiveSerialGate(input: LiveSerialGateInput): LiveSerialGateResult {
  const planHazir = Boolean(input.planHazirligi?.komutMetni?.trim());
  if (!planHazir) {
    return { allowed: false, reason: "plan-yok" };
  }

  if (!input.hizalamaDurumu) {
    return { allowed: false, reason: "hizalama-yok" };
  }

  if (
    input.hizalamaDurumu.durum !== "hazir" ||
    input.hizalamaDurumu.yanit.alignment?.blocked
  ) {
    return { allowed: false, reason: "hizalama-riskli" };
  }

  if (!input.kontrolDurumu) {
    return { allowed: false, reason: "kontrol-yok" };
  }

  if (input.kontrolDurumu.yanit.blocked) {
    return { allowed: false, reason: "kontrol-blocked" };
  }

  if (hasCollisionRisk(input.kontrolDurumu)) {
    return { allowed: false, reason: "carpisma-riski" };
  }

  if (hasDiagnostics(input.kontrolDurumu)) {
    return { allowed: false, reason: "kontrol-bulgusu" };
  }

  if (!input.canliOnay) {
    return { allowed: false, reason: "onay-yok" };
  }

  return { allowed: true, reason: "hazir" };
}
