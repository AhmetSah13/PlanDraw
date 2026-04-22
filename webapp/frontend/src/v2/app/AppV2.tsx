import React from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { ShellV2 } from "./ShellV2";
import { PlanYuklePage } from "../features/PlanYuklePage";
import { HizalaPage } from "../features/HizalaPage";
import { KontrolEtPage } from "../features/KontrolEtPage";
import { CalistirPage } from "../features/CalistirPage";
import { SonuclarPage } from "../features/SonuclarPage";

export function AppV2() {
  return (
    <Routes>
      <Route element={<ShellV2 />}>
        <Route path="/" element={<Navigate to="/plan-yukle" replace />} />
        <Route path="/plan-yukle" element={<PlanYuklePage />} />
        <Route path="/hizala" element={<HizalaPage />} />
        <Route path="/kontrol-et" element={<KontrolEtPage />} />
        <Route path="/calistir" element={<CalistirPage />} />
        <Route path="/sonuclar" element={<SonuclarPage />} />
      </Route>
    </Routes>
  );
}
