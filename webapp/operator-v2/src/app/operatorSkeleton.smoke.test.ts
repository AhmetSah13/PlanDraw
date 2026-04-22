import { describe, expect, it } from "vitest";
import { COPY, STAGE_LIST } from "../content";
import {
  applySimulationStreamEvent,
  createInitialExecutionSnapshot,
  markStopMissing,
  updateExecutionSnapshot,
} from "../lifecycle/execution/executionLifecycle";

describe("operator v2 iskeleti", () => {
  it("ana akış etiketlerini Türkçe ve tam sırada taşır", () => {
    expect(STAGE_LIST.map((asama) => asama.baslik)).toEqual([
      "Plan Yükle",
      "Hizala",
      "Kontrol Et",
      "Çalıştır",
      "Sonuçlar"
    ]);
  });

  it("execution lifecycle başlangıç ve güncelleme durumunu üretir", () => {
    const initial = createInitialExecutionSnapshot({ planHazir: false });
    const updated = updateExecutionSnapshot(initial, "hazir", "Plan çalıştırma için hazır.");

    expect(initial.faz).toBe("engelli");
    expect(initial.mesaj).toBe(COPY.ekranlar.calistir.mesajlar.planHazirDegil);
    expect(updated.faz).toBe("hazir");
    expect(updated.mesaj).toBe("Plan çalıştırma için hazır.");
    expect(updated.guncellenmeZamani).toBeGreaterThanOrEqual(initial.guncellenmeZamani);
  });

  it("ortak durum sözlüğünü eksiksiz taşır", () => {
    expect(COPY.durumlar).toEqual({
      hazir: "Hazır",
      engelli: "Engelli",
      bekliyor: "Bekliyor",
      calisiyor: "Çalışıyor",
      tamamlandi: "Tamamlandı",
      hata: "Hata",
      dikkat: "Dikkat"
    });
  });

  it("plan yükle ekranı için tek ana buton ve kaynak seçeneklerini taşır", () => {
    expect(COPY.butonlar.girdiyiHazirla).toBe("Girdiyi hazırla");
    expect(COPY.ekranlar.planYukle.kaynaklar.dxf.etiket).toBe("DXF dosyası");
    expect(COPY.ekranlar.planYukle.kaynaklar.dwg.etiket).toBe("DWG dosyası");
    expect(COPY.ekranlar.planYukle.kaynaklar.json.etiket).toBe("JSON plan dosyası");
    expect(COPY.ekranlar.planYukle.kaynaklar.manuel.etiket).toBe("Manuel plan metni");
  });

  it("job bulunamadı durumunu kırmızı hata yerine dikkat olarak işler", () => {
    const ready = createInitialExecutionSnapshot({ planHazir: true, girdiAdi: "plan.json" });
    const missing = applySimulationStreamEvent(ready, "error", { message: "job not found" });
    const stoppedMissing = markStopMissing(ready);

    expect(missing.ton).toBe("dikkat");
    expect(missing.faz).toBe("bulunamadi");
    expect(stoppedMissing.ton).toBe("dikkat");
    expect(stoppedMissing.mesaj).toBe(COPY.ekranlar.calistir.mesajlar.jobBulunamadi);
  });

  it("çalıştır ekranı için Türkçe aksiyon ve güvenli ayrım metinlerini taşır", () => {
    expect(COPY.butonlar.simulasyonuBaslat).toBe("Simülasyonu başlat");
    expect(COPY.butonlar.onKontrolCalistir).toBe("Ön kontrol çalıştır");
    expect(COPY.butonlar.canliCalistir).toBe("Canlı gönderimi başlat");
    expect(COPY.ekranlar.calistir.riskRozeti).toBe("Riskli aksiyon");
    expect(COPY.ekranlar.calistir.guvenliRozet).toBe("Güvenli akış");
  });

  it("hizala, kontrol et ve sonuçlar ekranları için Türkçe ana aksiyonları taşır", () => {
    expect(COPY.butonlar.hizalamayiDogrula).toBe("Hizalamayı doğrula");
    expect(COPY.butonlar.kontroluCalistir).toBe("Kontrolü çalıştır");
    expect(COPY.butonlar.ciktiyiHazirla).toBe("Çıktıyı hazırla");
    expect(COPY.ekranlar.hizala.ustBaslik).toBe("Hizala");
    expect(COPY.ekranlar.kontrolEt.ustBaslik).toBe("Kontrol Et");
    expect(COPY.ekranlar.sonuclar.ustBaslik).toBe("Sonuçlar");
  });
});
