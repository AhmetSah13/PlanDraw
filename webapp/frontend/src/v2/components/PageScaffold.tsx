import React from "react";

interface Props {
  baslik: string;
  aciklama: string;
  durum: string;
  children: React.ReactNode;
  aside: React.ReactNode;
}

export function PageScaffold({ baslik, aciklama, durum, children, aside }: Props) {
  return (
    <section className="sayfa">
      <header className="sayfa__ust">
        <div>
          <h1>{baslik}</h1>
          <p>{aciklama}</p>
        </div>
        <span className="durumRozeti">{durum}</span>
      </header>
      <div className="sayfa__icerik">
        <main className="panelYigin">{children}</main>
        <aside className="panelYigin">{aside}</aside>
      </div>
    </section>
  );
}
