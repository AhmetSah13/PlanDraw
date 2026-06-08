import { describe, expect, it } from "vitest";
import {
  buildWorkflowAvailability,
  getPostCompileNavigation,
  SECTION_IDS,
  SECTION_ORDER,
  SECTION_PURPOSE,
} from "./operatorFlow";

const baseInput = {
  backendOnline: true,
  busy: false,
  hasSelectedFile: true,
  hasCommands: true,
  compileStatus: "success" as const,
  simulationStatus: "waiting" as const,
  dryRunPassed: false,
  preflight: {
    blocked: false,
    commands_unrolled: "PEN UP\nMOVE 0 0\nPEN DOWN\nMOVE 1 1\nPEN UP",
    parser: [],
    analysis: [],
    stats: { move_count: 2, collision_count: 0, wall_proper_cross_count: 0 },
  },
  penSafeKnown: true,
  penSafe: true,
};

describe("operator v3 workflow gates", () => {
  it("demo derleme sonrası kontrolsüz şekilde loglara otomatik kaydırmaz", () => {
    expect(getPostCompileNavigation("demo")).toBeNull();
    expect(getPostCompileNavigation("manual")).toBe("derleme");
  });

  it("sol menü başlıkları farklı gerçek section hedeflerine sahiptir", () => {
    const ids = SECTION_ORDER.map((section) => SECTION_IDS[section]);
    expect(new Set(ids).size).toBe(ids.length);
    expect(SECTION_PURPOSE.plan).toContain("Hazır demo");
    expect(SECTION_PURPOSE.loglar).toContain("Komut akışı");
  });

  it("plan derlenmeden dry-run kapalıdır", () => {
    const gates = buildWorkflowAvailability({
      ...baseInput,
      hasCommands: false,
      compileStatus: "waiting",
    });
    expect(gates.canDryRun).toBe(false);
    expect(gates.dryRunReason).toContain("planı derleyin");
  });

  it("dry-run başarılı olmadan simülasyon kapalıdır", () => {
    const gates = buildWorkflowAvailability(baseInput);
    expect(gates.canSimulate).toBe(false);
    expect(gates.simulateReason).toContain("Dry-run");
  });

  it("backend offline olsa bile dry-run sonrası yerel simülasyon önizlemesine izin verir", () => {
    const gates = buildWorkflowAvailability({
      ...baseInput,
      backendOnline: false,
      dryRunPassed: true,
    });
    expect(gates.canSimulate).toBe(true);
    expect(gates.simulateReason).toBeNull();
  });

  it("blocked analiz canlı gönderimi kapatır", () => {
    const gates = buildWorkflowAvailability({
      ...baseInput,
      dryRunPassed: true,
      simulationStatus: "success",
      preflight: { ...baseInput.preflight, blocked: true },
    });
    expect(gates.canLive).toBe(false);
    expect(gates.liveReason).toContain("engelli");
  });

  it("dry-run ve simülasyon geçince canlı kapı açılır", () => {
    const gates = buildWorkflowAvailability({
      ...baseInput,
      dryRunPassed: true,
      simulationStatus: "success",
    });
    expect(gates.canLive).toBe(true);
    expect(gates.liveReason).toBeNull();
  });
});
