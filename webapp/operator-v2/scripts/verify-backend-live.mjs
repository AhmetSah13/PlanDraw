const API = process.env.OPERATOR_BACKEND_BASE ?? "http://127.0.0.1:8000";

async function post(path, body) {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const text = await res.text();
  let data;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { raw: text };
  }
  if (!res.ok) {
    throw new Error(`${path} -> HTTP ${res.status} :: ${JSON.stringify(data)}`);
  }
  return data;
}

function assert(cond, message) {
  if (!cond) throw new Error(message);
}

async function main() {
  console.log("[1/5] Plan Yükle -> /api/import_plan");
  const planPayload = {
    version: "v1",
    units: "mm",
    scale: 1.0,
    origin: { x: 0, y: 0 },
    segments: [
      { x1: 0, y1: 0, x2: 100, y2: 0 },
      { x1: 100, y1: 0, x2: 100, y2: 80 },
      { x1: 100, y1: 80, x2: 0, y2: 80 },
      { x1: 0, y1: 80, x2: 0, y2: 0 },
    ],
  };
  const plan = await post("/api/import_plan", planPayload);
  assert(plan.ok === true, "Plan import başarısız.");
  assert(typeof plan.commands_text === "string" && plan.commands_text.trim(), "commands_text üretilmedi.");
  assert(Array.isArray(plan.walls) && plan.walls.length > 0, "walls boş.");

  console.log("[2/5] Hizala -> /api/alignment/rigid_2d");
  const align = await post("/api/alignment/rigid_2d", {
    walls: plan.walls,
    control_points: [
      { cad_x: 0, cad_y: 0, site_x: 0, site_y: 0 },
      { cad_x: 100, cad_y: 0, site_x: 100, site_y: 0 },
    ],
    tolerance_m: 0.05,
  });
  assert(align.ok === true, "Hizalama başarısız.");
  assert(align.alignment, "alignment alanı yok.");

  console.log("[3/5] Kontrol Et -> /api/analyze");
  const kontrol = await post("/api/analyze", { commands_text: plan.commands_text });
  assert(typeof kontrol.blocked === "boolean", "blocked alanı yok.");
  assert(kontrol.stats, "stats alanı yok.");

  console.log("[4/5] Çalıştır -> /api/execute_serial (dry_run)");
  const dryRun = await post("/api/execute_serial", { text: plan.commands_text, dry_run: true });
  assert(typeof dryRun.status === "string", "execute_serial status alanı yok.");
  assert(typeof dryRun.command_count === "number", "execute_serial command_count alanı yok.");

  console.log("[5/5] Sonuçlar -> /api/export");
  const out = await post("/api/export", { text: plan.commands_text, format: "robot_v1" });
  assert(typeof out.content === "string" && out.content.length > 0, "export içeriği boş.");
  assert(typeof out.filename === "string" && out.filename.length > 0, "export filename boş.");

  console.log("Gerçek backend smoke doğrulaması başarılı.");
}

main().catch((err) => {
  console.error("Gerçek backend smoke doğrulaması başarısız:", err.message);
  process.exit(1);
});
