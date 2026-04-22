import React from "react";
import { NavLink, Outlet } from "react-router-dom";

const STAGES = [
  { to: "/prepare", label: "Prepare" },
  { to: "/align", label: "Align" },
  { to: "/plan", label: "Plan" },
  { to: "/execute", label: "Execute" },
  { to: "/monitor", label: "Monitor" },
];

export default function RewriteShell() {
  return (
    <div className="app-shell">
      <header className="app-topbar">
        <div className="app-topbar__row">
          <div className="app-brand">Operasyon Workspace</div>
          <nav className="stage-nav" aria-label="Operasyon aşamaları">
            {STAGES.map((s) => (
              <NavLink
                key={s.to}
                to={s.to}
                className={({ isActive }) =>
                  `stage-nav__item${isActive ? " stage-nav__item--active" : ""}`
                }
              >
                {s.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}
