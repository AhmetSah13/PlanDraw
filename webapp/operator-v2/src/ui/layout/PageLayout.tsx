import React from "react";

interface Props {
  baslik: string;
  aciklama: string;
  children: React.ReactNode;
  aside?: React.ReactNode;
}

export function PageLayout({ baslik, aciklama, children, aside }: Props) {
  return (
    <section className="page-layout">
      <header className="page-layout__header">
        <div>
          <h2>{baslik}</h2>
          <p>{aciklama}</p>
        </div>
      </header>
      <div className="page-layout__content">
        <div className="page-layout__main">{children}</div>
        {aside ? <aside className="page-layout__aside">{aside}</aside> : null}
      </div>
    </section>
  );
}
