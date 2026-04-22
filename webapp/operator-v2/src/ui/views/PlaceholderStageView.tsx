import React from "react";
import { COPY } from "../../content";
import { PageLayout } from "../layout/PageLayout";
import { StatusPanel } from "../components/StatusPanel";

interface Props {
  baslik: string;
  aciklama: string;
}

export function PlaceholderStageView({ baslik, aciklama }: Props) {
  return (
    <PageLayout
      baslik={baslik}
      aciklama={aciklama}
      aside={
        <StatusPanel
          baslik={COPY.ortak.kurulumDurumu}
          vurgu={COPY.ortak.siradakiAdim}
          mesaj={COPY.geriBildirim.dikkat.kurulumDevam}
        />
      }
    >
      <section className="panel">
        <p className="panel__eyebrow">{COPY.ortak.iskeletEkran}</p>
        <h3 className="panel__title">{baslik}</h3>
        <p className="panel__text">{COPY.ekranlar.placeholder.kartAciklamasi}</p>
      </section>
    </PageLayout>
  );
}
