import React from "react";

interface Props {
  baslik: string;
  mesaj: string;
  vurgu: string;
}

export function StatusPanel({ baslik, mesaj, vurgu }: Props) {
  return (
    <section className="panel">
      <p className="panel__eyebrow">{baslik}</p>
      <strong className="panel__value">{vurgu}</strong>
      <p className="panel__text">{mesaj}</p>
    </section>
  );
}
