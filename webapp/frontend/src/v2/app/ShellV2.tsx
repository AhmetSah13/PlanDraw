import React from "react";
import { NavLink, Outlet } from "react-router-dom";
import { COPY } from "../lib/copy";

export function ShellV2() {
  return (
    <div className="kabuk">
      <header className="ustBar">
        <div className="marka">{COPY.appTitle}</div>
        <nav className="adimNav" aria-label="Aşamalar">
          {COPY.stages.map((s) => (
            <NavLink key={s.path} to={s.path} className={({ isActive }) => `adimNav__item ${isActive ? "adimNav__item--aktif" : ""}`}>
              {s.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="govde">
        <Outlet />
      </main>
    </div>
  );
}
