import React from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { COPY, STAGE_LIST } from "../content";
import { PlanYukleView } from "../ui/views/PlanYukleView";
import { CalistirView } from "../ui/views/CalistirView";
import { HizalaView } from "../ui/views/HizalaView";
import { KontrolEtView } from "../ui/views/KontrolEtView";
import { SonuclarView } from "../ui/views/SonuclarView";

function StageNav() {
  return (
    <nav className="app-nav" aria-label={COPY.uygulama.anaAkisEtiketi}>
      {STAGE_LIST.map((asama) => (
        <NavLink
          key={asama.yol}
          to={asama.yol}
          className={({ isActive }) =>
            `app-nav__item ${isActive ? "app-nav__item--aktif" : ""}`
          }
        >
          <span className="app-nav__index">{asama.sira}</span>
          <span>{asama.baslik}</span>
        </NavLink>
      ))}
    </nav>
  );
}

export function OperatorAppShell() {
  return (
    <div className="app-shell">
      <header className="hero">
        <div>
          <p className="hero__eyebrow">{COPY.uygulama.urunTipi}</p>
          <h1>{COPY.uygulama.urunAdi}</h1>
          <p className="hero__text">{COPY.uygulama.urunAciklamasi}</p>
        </div>
        <div className="hero__status">
          <span className="hero__status-label">{COPY.uygulama.durumEtiketi}</span>
          <strong>{COPY.uygulama.kurulumDurumu}</strong>
        </div>
      </header>

      <StageNav />

      <main className="page-wrap">
        <Routes>
          <Route path="/" element={<Navigate to="/plan-yukle" replace />} />
          <Route path="/plan-yukle" element={<PlanYukleView />} />
          <Route
            path="/hizala"
            element={<HizalaView />}
          />
          <Route
            path="/kontrol-et"
            element={<KontrolEtView />}
          />
          <Route
            path="/calistir"
            element={<CalistirView />}
          />
          <Route
            path="/sonuclar"
            element={<SonuclarView />}
          />
        </Routes>
      </main>
    </div>
  );
}
