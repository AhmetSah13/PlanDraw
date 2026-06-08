import { describe, expect, it } from "vitest";
import {
  ApiError,
  buildAnalyzePayload,
  buildExecuteSerialPayload,
  formatUserError,
  formatValidationDetail,
  normalizeAnalyzeResponse,
} from "./api";
import type { AnalyzeResponse } from "../types/api";

const fullPreflight: AnalyzeResponse = {
  blocked: false,
  commands_unrolled: "SPEED 10\nMOVE 0 0\n",
  parser: [],
  analysis: [],
  stats: {
    move_count: 1,
    collision_count: 0,
    wall_proper_cross_count: 0,
  },
};

const partialPreflight = {
  blocked: false,
  commands_unrolled: "SPEED 10\nMOVE 0 0\n",
  stats: { move_count: 1 },
} as AnalyzeResponse;

describe("execute_serial payload", () => {
  it("dry-run için text ve dry_run alanlarını gönderir, preflight eklemez", () => {
    const body = buildExecuteSerialPayload("BEGIN\nEND", {
      dryRun: true,
      walls: [[0, 0, 10, 0]],
      preflight: partialPreflight,
    });
    expect(body).toEqual({
      text: "BEGIN\nEND",
      dry_run: true,
      walls: [[0, 0, 10, 0]],
    });
    expect(body).not.toHaveProperty("preflight");
  });

  it("canlı gönderim için tam preflight gönderir", () => {
    const body = buildExecuteSerialPayload("BEGIN\nEND", {
      dryRun: false,
      preflight: fullPreflight,
    });
    expect(body.dry_run).toBe(false);
    expect(body.preflight).toEqual(fullPreflight);
  });

  it("normalizeAnalyzeResponse parser ve analysis dizilerini korur", () => {
    const res = normalizeAnalyzeResponse({
      blocked: false,
      commands_unrolled: "MOVE 1 1",
      parser: [{ severity: "WARN", line: 1, message: "uyarı", text: "MOVE" }],
      analysis: [],
      stats: { move_count: 1, collision_count: 0 },
    });
    expect(res.parser).toHaveLength(1);
    expect(res.analysis).toEqual([]);
    expect(res.stats.move_count).toBe(1);
  });

  it("canlı öncesi final analiz için collision_mode error payload üretilebilir", () => {
    expect(buildAnalyzePayload("MOVE 1 1", [[0, 0, 1, 0]], "error")).toEqual({
      commands_text: "MOVE 1 1",
      walls: [[0, 0, 1, 0]],
      collision_mode: "error",
    });
    expect(buildAnalyzePayload("MOVE 1 1").collision_mode).toBe("warn");
  });
});

describe("422 ve serial hata mesajları", () => {
  it("formatValidationDetail FastAPI 422 detail özetler", () => {
    const summary = formatValidationDetail([
      { loc: ["body", "preflight", "parser"], msg: "Field required", type: "missing" },
    ]);
    expect(summary).toContain("preflight.parser");
    expect(summary).toContain("Field required");
  });

  it("formatUserError 422 ApiError mesajını Türkçe gösterir", () => {
    const err = new ApiError(
      "Backend doğrulama hatası: preflight.parser: Field required",
      422,
      { detail: [{ loc: ["body", "preflight", "parser"], msg: "Field required" }] },
    );
    expect(formatUserError(err)).toContain("Backend doğrulama hatası");
    expect(formatUserError(err)).toContain("preflight.parser");
  });

  it("formatUserError SERIAL_PORT_MISSING kodunu Türkçeleştirir", () => {
    const err = new ApiError("failed", 400, { error_detail: "SERIAL_PORT_MISSING" });
    expect(formatUserError(err)).toContain("Seri port ayarlı değil");
  });
});
