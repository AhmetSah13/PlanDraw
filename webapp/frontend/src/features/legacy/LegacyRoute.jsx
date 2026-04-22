import React from "react";
import { Link } from "react-router-dom";
import "./LegacyRoute.css";

export default function LegacyRoute() {
  return (
    <div className="oc-legacy-wrap">
      <div className="oc-legacy-bar">
        <Link className="oc-legacy-bar__link" to="/prepare">
          ← Operasyon konsoluna dön
        </Link>
      </div>
      <div className="panel">
        <h2>Legacy arayuz kapatildi</h2>
        <p>Yeni orchestration architecture aktif. Tum akislar yeni ekranlarda yonetiliyor.</p>
      </div>
    </div>
  );
}
