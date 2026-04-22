import React from "react";
import AlignmentPreviewPanel from "./AlignmentPreviewPanel.jsx";

export default function AlignPreviewCard({ preSvg, postSvg, hasWalls }) {
  return (
    <section className="align2-card align2-card--preview" aria-label="Önizleme">
      <div className="align2-card__head">
        <h2 className="align2-card__h">Önizleme</h2>
        <p className="align2-muted">Ön (CAD) ve Son (saha) SVG; hizalamayı çalıştırınca güncellenir.</p>
      </div>
      <div className="align2-card__body">
        <AlignmentPreviewPanel preSvg={preSvg} postSvg={postSvg} hasWalls={hasWalls} />
      </div>
    </section>
  );
}

