import React from "react";

const LABELS = {
  missing: "Eksik veri",
  ready: "Hazır",
  warning: "Uyarı var",
  blocked: "Engelli",
  running: "Çalışıyor",
  done: "Tamamlandı",
  error: "Hata",
  idle: "Bekliyor",
};

export default function StageStatusBadge({ status, title }) {
  const label = LABELS[status] ?? status;
  return (
    <span className={`oc-badge oc-badge--${status}`} title={title || label}>
      {label}
    </span>
  );
}
