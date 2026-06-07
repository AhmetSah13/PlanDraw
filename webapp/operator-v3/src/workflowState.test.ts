import { describe, expect, it } from "vitest";
import { tr } from "./content/tr";
import { formatUserError } from "./services/api";
import {
  buildDryRunFeedback,
  buildSimFeedback,
  formatActivityLog,
  formatDryRunLog,
  isDryRunSuccess,
  newPlanActivityLog,
  pipelineAfterCompile,
  pipelineAfterFileSelect,
  parseActivityLogLevel,
} from "./lib/workflowState";

describe("workflowState", () => {
  it("yeni dosya seçilince pipeline upload hazır, diğerleri bekliyor", () => {
    const p = pipelineAfterFileSelect();
    expect(p.upload).toBe("ready");
    expect(p.analyze).toBe("waiting");
    expect(p.compile).toBe("waiting");
    expect(p.simulate).toBe("waiting");
    expect(p.send).toBe("waiting");
  });

  it("derleme sonrası simülasyon ve canlı gönderim sıfırlanır", () => {
    const p = pipelineAfterCompile(true);
    expect(p.upload).toBe("success");
    expect(p.analyze).toBe("success");
    expect(p.compile).toBe("success");
    expect(p.simulate).toBe("waiting");
    expect(p.send).toBe("waiting");
  });

  it("newPlanActivityLog önceki logları tek INFO satırı ile değiştirir", () => {
    expect(newPlanActivityLog("demo_square_room.dxf")).toEqual([
      "[INFO] Yeni plan seçildi: demo_square_room.dxf",
    ]);
  });

  it("formatActivityLog ve parseActivityLogLevel prefix üretir", () => {
    const line = formatActivityLog("OK", "Pen-safe compile tamamlandı");
    expect(line).toBe("[OK] Pen-safe compile tamamlandı");
    expect(parseActivityLogLevel(line)).toBe("OK");
    expect(parseActivityLogLevel("düz metin")).toBeNull();
  });

  it("isDryRunSuccess backend yanıtını doğru yorumlar", () => {
    expect(isDryRunSuccess({ status: "completed", message: "ok" })).toBe(true);
    expect(isDryRunSuccess({ status: "failed", message: "x", ok: false })).toBe(false);
    expect(isDryRunSuccess({ status: "unknown", message: "x", ok: true })).toBe(true);
  });

  it("buildDryRunFeedback başarı mesajını net gösterir", () => {
    const fb = buildDryRunFeedback("success", {
      status: "completed",
      message: "dry_run artifact written",
      command_count: 12,
    });
    expect(fb.title).toBe("Dry-run tamamlandı");
    expect(fb.message).toContain("robota gönderilmeden");
    expect(fb.detail).toContain("12 komut");
  });

  it("buildSimFeedback stream bağlı değil uyarısını içerir", () => {
    const fb = buildSimFeedback("success", "job-abc-123");
    expect(fb.message).toContain("job-abc-123");
    expect(fb.detail).toContain("Canlı animasyon henüz bağlı değil");
  });

  it("formatDryRunLog OK prefix kullanır", () => {
    expect(formatDryRunLog(true)).toMatch(/^\[OK\]/);
    expect(formatDryRunLog(false, "SERIAL_PORT_MISSING")).toMatch(/^\[ERR\]/);
  });
});

describe("workflow UI copy", () => {
  it("dry-run buton metni açıklayıcı Türkçe ifade kullanır", () => {
    expect(tr.control.dryRun).toBe("Komutları Test Et (Dry-run)");
    expect(tr.control.dryRunHint).toContain("Robot hareket etmez");
  });

  it("formatUserError simülasyon hatalarını Türkçe döndürür", () => {
    expect(formatUserError(new TypeError("network"))).toContain("Backend bağlantısı");
  });
});
