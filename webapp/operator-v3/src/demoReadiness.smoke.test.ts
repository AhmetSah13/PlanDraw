import { readFileSync } from "fs";
import { dirname, resolve } from "path";
import { fileURLToPath } from "url";
import { describe, expect, it } from "vitest";

const testDir = dirname(fileURLToPath(import.meta.url));
import { tr } from "./content/tr";
import {
  ApiError,
  extractCommandsText,
  formatUserError,
  isSupportedPlanFile,
} from "./services/api";
import { DEMO_PLANS } from "./services/demoPlans";

describe("LayoutBot V3 demo readiness", () => {
  it("LayoutBot başlığı ve marka metinlerini taşır", () => {
    expect(tr.brand.name).toBe("LayoutBot");
    expect(tr.brand.commandCenter).toBe("Command Center");
    expect(tr.brand.operatorPanel).toBe("LayoutBot Operatör Paneli");

    const html = readFileSync(resolve(testDir, "../index.html"), "utf-8");
    expect(html).toContain("LayoutBot Command Center");
  });

  it("demo telemetri metinlerini dürüst donanım durumu ile taşır", () => {
    expect(tr.telemetry.firmwarePass).toBe("PASS");
    expect(tr.telemetry.motorsWaiting).toBe("Donanım testi bekliyor");
    expect(tr.telemetry.penSafeActive).toBe("Aktif");
    expect(tr.telemetry.liveRequiresHardware).toBe("Fiziksel test gerektirir");
  });

  it("demo akış adımlarını ve örnek plan listesini taşır", () => {
    expect(tr.demo.hint).toContain("DXF yükle");
    expect(tr.demo.hint).toContain("dry-run");
    expect(DEMO_PLANS).toHaveLength(3);
    expect(DEMO_PLANS.map((p) => p.label)).toEqual([
      "Basit kare oda",
      "İki kopuk çizgi",
      "Oda + kapı boşluğu",
    ]);
  });

  it("desteklenmeyen dosya uyarısı için isSupportedPlanFile reddeder", () => {
    const dxf = new File(["x"], "plan.dxf", { type: "application/dxf" });
    const json = new File(["{}"], "plan.json", { type: "application/json" });
    const txt = new File(["x"], "notes.txt", { type: "text/plain" });

    expect(isSupportedPlanFile(dxf)).toBe(true);
    expect(isSupportedPlanFile(json)).toBe(true);
    expect(isSupportedPlanFile(txt)).toBe(false);
    expect(tr.errors.unsupportedFile).toContain("DXF");
  });

  it("formatUserError ağ ve API hatalarını Türkçe döndürür", () => {
    expect(formatUserError(new TypeError("network"))).toContain("Backend bağlantısı");
    expect(formatUserError(new ApiError("Seri port meşgul", 409, {}))).toBe("Seri port meşgul");
    expect(formatUserError(new SyntaxError("invalid"))).toContain("JSON plan");
  });

  it("extractCommandsText yanıt alanlarından güvenli komut metni çıkarır", () => {
    expect(
      extractCommandsText({
        ok: true,
        commands_text_optimized: "BEGIN\nPEN UP\nEND",
      }),
    ).toBe("BEGIN\nPEN UP\nEND");

    expect(
      extractCommandsText({
        ok: true,
        commands_text_raw: "BEGIN\nMOVE 1 2\nEND",
        commands_text_optimized: "",
      }),
    ).toBe("BEGIN\nMOVE 1 2\nEND");

    expect(extractCommandsText({ ok: true })).toBe("");
  });
});
