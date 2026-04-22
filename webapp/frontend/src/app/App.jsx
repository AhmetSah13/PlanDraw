import React from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import RewriteShell from "./layout/RewriteShell.jsx";
import PreparePage from "../features/prepare/PreparePage.jsx";
import AlignPage from "../features/align/AlignPage.jsx";
import PlanPage from "../features/plan/PlanPage.jsx";
import ExecutePage from "../features/execute/ExecutePage.jsx";
import MonitorPage from "../features/monitor/MonitorPage.jsx";
import LegacyRoute from "../features/legacy/LegacyRoute.jsx";

/**
 * Kök router: yeni operasyon konsolu varsayılan; /legacy eski PlanDraw (src/App.jsx).
 */
export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/legacy/*" element={<LegacyRoute />} />
        <Route
          element={
            <RewriteShell />
          }
        >
          <Route path="/" element={<Navigate to="/prepare" replace />} />
          <Route path="/prepare" element={<PreparePage />} />
          <Route path="/align" element={<AlignPage />} />
          <Route path="/plan" element={<PlanPage />} />
          <Route path="/execute" element={<ExecutePage />} />
          <Route path="/monitor" element={<MonitorPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
