import React, { useState } from "react";

export default function AlignmentPreviewPanel({ preSvg, postSvg, hasWalls }) {
  const [tab, setTab] = useState("pre");

  if (!preSvg && !postSvg) {
    return (
      <div className="align2-preview">
        <h3 className="align2-card__h">Önizleme</h3>
        <p className="align2-muted">
          {hasWalls
            ? "Hizalamayı çalıştırdığınızda CAD (ön) ve saha (son) SVG önizlemesi burada görünür."
            : "Duvar segmenti yok; önizleme boş veya minimal olabilir. Yine de kontrol noktaları ile dönüşüm hesaplanır."}
        </p>
        <div className="align2-preview__placeholder">Henüz SVG yok</div>
      </div>
    );
  }

  const svg = tab === "pre" ? preSvg : postSvg;
  return (
    <div className="align2-preview">
      <div className="align2-preview__tabs">
        <button
          type="button"
          className={tab === "pre" ? "align2-tab align2-tab--active" : "align2-tab"}
          onClick={() => setTab("pre")}
        >
          Ön (CAD)
        </button>
        <button
          type="button"
          className={tab === "post" ? "align2-tab align2-tab--active" : "align2-tab"}
          onClick={() => setTab("post")}
        >
          Son (saha)
        </button>
      </div>
      <div className="align2-preview__svg" dangerouslySetInnerHTML={{ __html: svg }} />
    </div>
  );
}
