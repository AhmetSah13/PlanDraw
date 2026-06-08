import { describe, expect, it } from "vitest";
import {
  SIMULATION_MIN_DURATION_MS,
  buildSimulationPreview,
  buildSimulationSegments,
  createIdlePlayback,
  getSimulationProgress,
  parseCommandsToSegments,
  parseCommandsToSimulationSegments,
  pathPointsToSegments,
  resetSimulationPlayback,
  startPlayback,
  tickPlayback,
} from "./commandSimulation";

const SAMPLE = `BEGIN
PEN UP
MOVE 0 0
PEN DOWN
MOVE 100 0
MOVE 100 50
PEN UP
MOVE 200 50
PEN DOWN
MOVE 200 100
END`;

describe("commandSimulation", () => {
  it("komutlardan simülasyon segmentleri çıkarır", () => {
    const segs = parseCommandsToSegments(SAMPLE);
    expect(segs.length).toBeGreaterThanOrEqual(4);
    expect(segs.some((s) => s.kind === "draw")).toBe(true);
    expect(segs.some((s) => s.kind === "travel")).toBe(true);
  });

  it("PEN UP travel, PEN DOWN draw ayrımını doğru yapar", () => {
    const segs = parseCommandsToSegments(SAMPLE);
    const drawSeg = segs.find((s) => s.x2 === 100 && s.y2 === 0);
    const travelSeg = segs.find((s) => s.x2 === 200 && s.y2 === 50 && s.kind === "travel");
    expect(drawSeg?.kind).toBe("draw");
    expect(travelSeg?.kind).toBe("travel");
  });

  it("komut yoksa pathPoints yedek segment üretir", () => {
    const segs = buildSimulationSegments("", [
      [0, 0],
      [10, 0],
      [10, 10],
    ]);
    expect(segs).toHaveLength(2);
    expect(segs.every((s) => s.kind === "draw")).toBe(true);
  });

  it("simülasyon başlatınca progress sıfırlanır", () => {
    const segs = pathPointsToSegments([
      [0, 0],
      [50, 0],
    ]);
    const pb = startPlayback(1, segs);
    expect(pb.active).toBe(true);
    expect(pb.progress).toBe(0);
    expect(pb.completed).toBe(false);
  });

  it("tickPlayback ilerleme artırır ve tamamlar", () => {
    const segs = parseCommandsToSegments(SAMPLE);
    let pb = startPlayback(2, segs);
    for (let i = 0; i < 500; i++) {
      pb = tickPlayback(pb, segs, 16, 5000);
      if (pb.completed) break;
    }
    expect(pb.completed).toBe(true);
    expect(pb.progress).toBe(100);
  });

  it("MOVE_TO, DRAW_TO, DRAW ve PEN_UNDERSCORE komutlarından preview üretir", () => {
    const parsed = parseCommandsToSimulationSegments(`BEGIN
PEN_UP
MOVE_TO 0 0
PEN_DOWN
DRAW_TO 20 0
PEN_UP
MOVE 30 0
DRAW 30 10
END`);
    expect(parsed.segments.some((s) => s.kind === "draw")).toBe(true);
    expect(parsed.segments.some((s) => s.kind === "travel")).toBe(true);
    expect(parsed.warnings).toHaveLength(0);
  });

  it("TURN/FORWARD ve MOVE_REL komutları simülasyon segmentine çevrilir", () => {
    const segs = parseCommandsToSegments(`PEN DOWN
FORWARD 10
TURN 90
FORWARD 5
MOVE_REL 5 0`);
    expect(segs).toHaveLength(3);
    expect(segs.every((s) => s.kind === "draw")).toBe(true);
  });

  it("bozuk satır parser'ı çökertmez ve uyarı döner", () => {
    const parsed = parseCommandsToSimulationSegments(`PEN DOWN
MOVE 10 0
BOZUK KOMUT
MOVE 20 0`);
    expect(parsed.segments).toHaveLength(2);
    expect(parsed.warnings[0].message).toContain("atladı");
  });

  it("preview önce commandsText, yoksa pathPoints kullanır", () => {
    expect(buildSimulationPreview("PEN DOWN\nMOVE 10 0", [[0, 0], [1, 1]]).source).toBe("commands");
    expect(buildSimulationPreview("", [[0, 0], [1, 1]]).source).toBe("pathPoints");
    expect(buildSimulationPreview("", []).error).toContain("Önce planı derleyin");
  });

  it("kısa planlarda minimum izlenebilir animasyon süresi uygular", () => {
    const segs = parseCommandsToSegments("PEN DOWN\nMOVE 1 0");
    const pb = startPlayback(3, segs);
    expect(pb.durationMs).toBeGreaterThanOrEqual(SIMULATION_MIN_DURATION_MS);
    expect(getSimulationProgress(pb)).toBe(0);
  });

  it("createIdlePlayback yeni dosya reset durumunu temsil eder", () => {
    const idle = resetSimulationPlayback();
    expect(idle.active).toBe(false);
    expect(idle.progress).toBe(0);
    expect(idle.completed).toBe(false);
    expect(createIdlePlayback().elapsedMs).toBe(0);
  });
});
