import { apiBaseUrl, executeHeaders, httpForm, httpJson } from "./http.js";

export const prepareService = {
  importDxf(file) {
    const fd = new FormData();
    fd.append("file", file);
    return httpForm("/api/import_dxf", fd);
  },
  importDwg(file) {
    const fd = new FormData();
    fd.append("file", file);
    return httpForm("/api/import_dwg", fd);
  },
  importJson(file) {
    return file
      .text()
      .then((text) => JSON.parse(text))
      .then((payload) => httpJson("/api/import_plan", { method: "POST", body: payload }));
  },
  compilePlan(planText) {
    return httpJson("/api/compile_plan", { method: "POST", body: { plan_text: planText } });
  },
  analyze(commandsText) {
    return httpJson("/api/analyze", { method: "POST", body: { commands_text: commandsText } });
  },
};

export const alignService = {
  run(payload) {
    return httpJson("/api/alignment/rigid_2d", { method: "POST", body: payload });
  },
};

export const planService = {
  optimize(commandsText) {
    return httpJson("/api/analyze", { method: "POST", body: { commands_text: commandsText } }).then((data) => ({
      blocked: Boolean(data?.blocked),
      commands_text: data?.commands_unrolled ?? commandsText,
      raw_path_points: Array.isArray(data?.stats?.path_points) ? data.stats.path_points : [],
      stats: data?.stats ?? null,
    }));
  },
  simulate(commandsText) {
    return httpJson("/api/simulate", { method: "POST", body: { text: commandsText } });
  },
};

export const executeService = {
  createJob(commandsText) {
    return httpJson("/api/jobs", { method: "POST", body: { text: commandsText } });
  },
  stopJob(jobId) {
    return httpJson(`/api/jobs/${encodeURIComponent(jobId)}/stop`, { method: "POST" });
  },
  executeSerial(commandsText, dryRun) {
    return httpJson("/api/execute_serial", {
      method: "POST",
      headers: executeHeaders(),
      body: { text: commandsText, dry_run: dryRun },
    });
  },
  streamUrl(jobId) {
    return `${apiBaseUrl()}/api/jobs/${encodeURIComponent(jobId)}/stream`;
  },
};
