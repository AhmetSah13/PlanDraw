import React from "react";
import { Link } from "react-router-dom";
import NextStepCta from "../flow/NextStepCta.jsx";
import StageStatusBadge from "../flow/StageStatusBadge.jsx";

function fmtNum(x) {
  if (x == null) return "—";
  const n = Number(x);
  if (!Number.isFinite(n)) return String(x);
  return n.toFixed(6);
}

function formatWhen(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("tr-TR");
  } catch {
    return String(iso);
  }
}

/**
 * Monitor sağ sütun: oturumdaki son hizalama özeti (salt okunur).
 */
export default function MonitorAlignmentCard({ align }) {
  const a = align?.alignment;
  const gate = align?.gate ?? "none";

  if (gate === "none") {
    return (
      <div className="oc-align-card oc-align-card--missing">
        <h2 className="oc-align-card__h">Hizalama özeti</h2>
        <p className="oc-align-card__muted">Hizalama yapılmadı — oturumda kayıt yok.</p>
        <NextStepCta
          primary={{ to: "/align", label: "Align ekranına git", hint: "CAD ↔ saha eşlemesi" }}
        />
      </div>
    );
  }

  if (gate === "blocked") {
    return (
      <div className="oc-align-card oc-align-card--blocked">
        <h2 className="oc-align-card__h">Hizalama özeti</h2>
        <div className="oc-align-bridge__row">
          <StageStatusBadge status="blocked" title="Engelli" />
          <span className="oc-align-bridge__msg">Engelli — tolerans dışı veya geometri.</span>
        </div>
        <ul className="oc-align-bridge__list oc-align-bridge__list--compact">
          <li>
            Zaman: <strong>{formatWhen(align.updatedAt)}</strong>
          </li>
          <li>
            Dönüşüm: <strong>{a?.transform_type ?? "—"}</strong> · nokta: <strong>{a?.point_count ?? "—"}</strong>
          </li>
          <li>
            residual ort / max: <strong>{fmtNum(a?.residual_mean_m)}</strong> / <strong>{fmtNum(a?.residual_max_m)}</strong> m
          </li>
          <li>
            Tolerans: <strong>{fmtNum(a?.tolerance_m)}</strong> m
          </li>
        </ul>
        {(a?.reasons?.[0] || a?.notes?.[0]) && (
          <p className="oc-align-card__muted">
            <strong>Özet:</strong> {a?.reasons?.[0] || a?.notes?.[0]}
          </p>
        )}
        <p className="oc-align-card__muted">
          Düzeltme için <Link to="/align">Align</Link> veya <Link to="/execute">Execute</Link> öncesi Plan.
        </p>
        <NextStepCta
          primary={{ to: "/align", label: "Align’da düzelt", hint: "Kontrol noktası / tolerans" }}
          secondary={{ to: "/execute", label: "Execute", hint: "Durumu kontrol" }}
        />
      </div>
    );
  }

  return (
    <div className="oc-align-card oc-align-card--ok">
      <h2 className="oc-align-card__h">Hizalama özeti</h2>
      <div className="oc-align-bridge__row">
        <StageStatusBadge status="ready" title="İzin verildi" />
        <span className="oc-align-bridge__msg">Son hizalama uygundu (izin verildi).</span>
      </div>
      <ul className="oc-align-bridge__list oc-align-bridge__list--compact">
        <li>
          Zaman: <strong>{formatWhen(align.updatedAt)}</strong>
        </li>
        <li>
          Dönüşüm: <strong>{a?.transform_type ?? "—"}</strong> · nokta: <strong>{a?.point_count ?? "—"}</strong>
        </li>
        <li>
          residual ort / max: <strong>{fmtNum(a?.residual_mean_m)}</strong> / <strong>{fmtNum(a?.residual_max_m)}</strong> m
        </li>
        <li>
          Tolerans: <strong>{fmtNum(a?.tolerance_m)}</strong> m
        </li>
      </ul>
      {(a?.reasons?.length > 0 || a?.notes?.length > 0) && (
        <p className="oc-align-card__muted">
          {a?.notes?.[0] && <span>{a.notes[0]} </span>}
          {a?.reasons?.[0] && <span>({a.reasons[0]})</span>}
        </p>
      )}
      <Link className="oc-align-link" to="/align">
        Align ayrıntısı
      </Link>
    </div>
  );
}
