# PlanDraw / NewBot — Stratejik Teknik Değerlendirme

**Tarih:** 2025-02-27  
**Kapsam:** DXF destek analizi, pipeline ölçeklenebilirliği, mimari öneriler, üniversite projesi kapsam tanımı.

---

## 1. Mevcut Mimariyle Gerçek DXF Planların Çizilebilirliği

### Desteklenen Entity'ler (gerçekten kullanılan)
- **LINE** — doğrudan segment
- **LWPOLYLINE** — düz segment zinciri (bulge=0)
- **POLYLINE + VERTEX** — düz segment zinciri (bulge=0)

### Desteklenmeyen / Atlanan
- ARC, CIRCLE, SPLINE
- HATCH
- INSERT (bloklar)
- XREF
- DIMENSION, TEXT

### Gerçekçi Çizilebilirlik Tahmini

| Plan Tipi | Tahmini Çizilebilirlik | Açıklama |
|-----------|------------------------|----------|
| **Basit ev planı** (internet, amatör) | **%15–35** | Genelde LINE/LWPOLYLINE ağırlıklı; ARC (köşe yuvarlamaları), INSERT (kapı/pencere sembolleri) sık. Duvar çizgileri çoğunlukla çizilebilir, detaylar kaybolur. |
| **Profesyonel mimari plan** | **%5–15** | Bloklar (INSERT), HATCH (taramalar), ARC, DIMENSION, TEXT yoğun. Sadece bazı katmanlardaki düz çizgiler kullanılabilir. |
| **CAD üretim çizimi** | **%2–8** | Bloklar, XREF, ölçüler, notlar baskın. Geometri genelde LINE/LWPOLYLINE olsa bile katman karmaşası ve bloklar nedeniyle çoğu içerik atlanır. |
| **CNC temiz DXF** | **%85–98** | Konturlar genelde LWPOLYLINE veya POLYLINE; ARC varsa bile az. Bu tür dosyalar mevcut pipeline ile iyi çalışır. |

**Özet:** Mevcut mimariyle gerçek mimari DXF’lerin büyük çoğunluğu **kısmen veya hiç** çizilemez. Sadece CNC/kesim odaklı, düz segment ağırlıklı dosyalar yüksek oranda desteklenir.

---

## 2. Pipeline’ın Ölçeklenebilirliği

### INSERT (Blok Patlatma)
- **Yapısal uyum:** Evet. `NormalizedPlan` sadece `SegmentIn` listesi bekliyor; blok patlatma sonrası segment üretimi mevcut yapıya uyumlu.
- **Zorluk:** BLOCKS bölümünü parse etmek, INSERT’leri matris transform ile yerleştirmek, recursive blok referansları (blok içinde blok).
- **Sonuç:** Mimari olarak uyumlu; ek bir preprocessing modülü ile eklenebilir.

### ARC / SPLINE Discretizasyonu
- **Yapısal uyum:** Evet. Eğriler chord/segment zincirine dönüştürülür; çıktı yine `SegmentIn` listesi.
- **Zorluk:** ARC: açı, merkez, yarıçap → chord sayısı (tolerans). SPLINE: kontrol noktaları, knot vektörü → NURBS evaluator veya ezdxf kullanımı.
- **Sonuç:** Pipeline değişmeden, import aşamasında eğri→segment dönüşümü yeterli.

### Katman Filtreleme (örn. sadece WALL)
- **Mevcut durum:** `layer_whitelist` ve `layer_blacklist` zaten var.
- **Eksik:** Kullanıcı arayüzünden katman seçimi ve inspect sonuçlarına dayalı filtreleme.
- **Sonuç:** Altyapı hazır; UI ve API tarafında tamamlanması gerekiyor.

### Entity Temizleme Aşaması (Normalizasyondan Önce)
- **Yapısal uyum:** Evet. `Raw DXF → Preprocess → NormalizedPlan` zinciri mevcut pipeline’a uyumlu.
- **Örnek adımlar:** Duplicate segment silme, çok kısa segment birleştirme, self-intersection temizleme.
- **Sonuç:** Preprocessing katmanına eklenebilir; mimari değişiklik gerektirmez.

**Özet:** Pipeline, INSERT, ARC/SPLINE, katman filtreleme ve entity temizleme için **yapısal olarak ölçeklenebilir**. Zorluk, DXF parse ve preprocessing mantığında; downstream (PathGenerator, scenario_analysis) değişmez.

---

## 3. DXF Preprocessing Katmanı — Mimari Öneri

### Önerilen Akış

```
Raw DXF (ASCII/Binary)
    ↓
┌─────────────────────────────────────────────────────────────┐
│  PREPROCESSING LAYER                                         │
│  1. Parse (mevcut parse_dxf_ascii veya ezdxf)                │
│  2. Block explosion (INSERT → inline geometry)                │
│  3. Curve discretization (ARC, CIRCLE, SPLINE → chord chain)  │
│  4. Layer filter (whitelist/blacklist)                        │
│  5. Entity filter (sadece çizilebilir tipler)                 │
│  6. Cleanup (duplicate, zero-length, optional merge)          │
│  7. Output: SegmentIn[] (veya ara format)                     │
└─────────────────────────────────────────────────────────────┘
    ↓
NormalizedPlan (mevcut)
    ↓
normalize_plan (mevcut)
    ↓
Plan → PathGenerator → scenario_analysis → export (mevcut)
```

### Tasarım Prensipleri
- **Tek sorumluluk:** Preprocessing sadece DXF → segment dönüşümünden sorumlu.
- **Opsiyonel adımlar:** Block explosion, curve discretization, cleanup ayrı flag’lerle açılıp kapatılabilir.
- **Determinizm:** Aynı DXF + aynı parametreler → aynı segment listesi.
- **Hata yönetimi:** Desteklenmeyen entity’ler atlanır; uyarı listesi döner; hiç segment kalmazsa hata.

### Bu Katman Yeterli mi?
**Evet**, aşağıdakiler için:
- INSERT patlatma
- ARC/CIRCLE/SPLINE → segment
- Katman filtreleme
- Temel entity temizleme

**Yetersiz** kalacağı alanlar:
- XREF (harici referanslar — dosya yükleme, path çözümleme)
- HATCH (tarama pattern’leri — karmaşık geometri)
- DIMENSION (ölçü çizgileri — genelde çizim dışı)
- TEXT (metin — genelde çizim dışı)

Bu sınırlar, üniversite projesi kapsamında kabul edilebilir.

---

## 4. Tam CAD Motoru Sınırı — Neyi Desteklememeli?

### Desteklenmemesi Gerekenler (Açıkça)

| Özellik | Neden |
|---------|-------|
| **XREF** | Harici dosya bağımlılığı, path çözümleme, versiyonlama — tam CAD davranışı |
| **HATCH** | Pattern tanımları, boundary hesaplama, tarama açıları — karmaşık |
| **DIMENSION** | Ölçü çizgileri çizim değil; robot için anlamsız |
| **TEXT / MTEXT** | Metin çizimi ayrı bir problem (font, hizalama) |
| **Binary DXF** | Öncelik düşük; ASCII yeterli ise ertelenebilir |
| **3D entity’ler** | 3D FACE, 3DSOLID vb. — 2D plan odaklı sistemde gereksiz |
| **OLE / Image** | Gömülü nesneler — çizim dışı |
| **Viewport / Layout** | Çoklu görünüm — karmaşıklık artışı |

### Sınır Çizgisi
- **ARC/CIRCLE/SPLINE:** Discretizasyon ile makul sürede eklenebilir; **desteklenmeli**.
- **INSERT:** Blok patlatma orta zorlukta; **desteklenmeli**.
- **HATCH:** Sadece boundary polyline çıkarılabilirse sınırlı destek düşünülebilir; aksi halde **desteklenmemeli**.

**Özet:** Tam CAD motoru olmaya çalışmayın. Hedef: **mimari planlardaki duvar/kontur geometrisini çıkarmak**. Ölçü, metin, tarama, harici referanslar dışarıda bırakılmalı.

---

## 5. Üniversite Projesi İçin Teknik Kapsam Tanımı

### Kabul Edilebilir DXF Alt Kümesi (Resmi Tanım)

**Desteklenen entity’ler:**
- LINE
- LWPOLYLINE (bulge=0 veya bulge≠0 → discretize)
- POLYLINE + VERTEX (düz veya arc vertex → discretize)
- ARC, CIRCLE (discretize)
- SPLINE (discretize)
- INSERT (explode → yukarıdaki tiplere indirgenmiş geometry)

**Desteklenmeyen (açıkça belirtilmiş):**
- HATCH, XREF, DIMENSION, TEXT, MTEXT
- 3D entity’ler, OLE, Image
- Binary DXF (opsiyonel, v2)

**Birim:** Sadece `$INSUNITS` ile tanımlı birimler (mm, m, cm, in, ft). Bilinmeyen birimde uyarı + mm varsayımı.

**Katman:** Whitelist/blacklist ile filtreleme. Varsayılan: tüm katmanlar (0 dahil).

**Dosya boyutu:** Makul limit (örn. 10 MB ASCII) — DoS önlemi.

### Kullanıcı Sözleşmesi (Önerilen UI Metni)

> "PlanDraw, mimari planlardaki **duvar ve kontur çizgilerini** çizmek için tasarlanmıştır. DXF dosyanız LINE, LWPOLYLINE, POLYLINE, ARC, CIRCLE, SPLINE ve INSERT (blok) içerebilir. Ölçüler, metinler ve taramalar desteklenmez. En iyi sonuç için CNC veya sadeleştirilmiş plan dosyaları önerilir."

### Başarı Kriteri
- Verilen "kabul edilebilir" DXF’ten **deterministik** segment listesi üretimi
- PathGenerator + scenario_analysis ile güvenli çizim komutu üretimi
- Export: robot_v1, gcode_lite

---

## 6. Önerilen Yol Haritası

### Faz 1 — Minimal Gerçekçi Alt Küme (Öncelik: Yüksek)
**Süre:** 2–4 hafta  
**Hedef:** Mevcut destek + ARC/CIRCLE + katman UI

- [ ] ARC, CIRCLE discretization (chord toleransı parametresi)
- [ ] Katman seçimi UI (inspect sonuçlarına dayalı whitelist/blacklist)
- [ ] "Desteklenmeyen entity" uyarı raporu (kaç ARC, INSERT atlandı vb.)
- [ ] Dokümantasyon: Kabul edilebilir DXF tanımı

**Çıktı:** Basit ev planları ve CNC DXF’ler daha iyi çalışır.

---

### Faz 2 — Orta Karmaşıklık (Öncelik: Orta)
**Süre:** 4–6 hafta  
**Hedef:** SPLINE + INSERT + temel cleanup

- [ ] SPLINE discretization (NURBS → chord chain, ezdxf veya basit algoritma)
- [ ] INSERT block explosion (recursive bloklar dahil, matris transform)
- [ ] Preprocessing katmanı modüler yapı (adımlar ayrı fonksiyonlar)
- [ ] Duplicate/zero-length segment cleanup (normalize öncesi)

**Çıktı:** Profesyonel planlarda duvar geometrisi büyük oranda çıkarılabilir.

---

### Faz 3 — İleri (Öncelik: Düşük, İhtiyaç Halinde)
**Süre:** Belirsiz  
**Hedef:** Kenar durumlar ve kalite

- [ ] HATCH boundary extraction (sadece dış kontur, basit pattern’ler)
- [ ] Binary DXF desteği
- [ ] Self-intersection temizleme
- [ ] Segment budget + LOD (çok büyük planlarda sadeleştirme)

**Çıktı:** Daha geniş dosya yelpazesi; karmaşıklık belirgin şekilde artar.

---

## Sonuç Tablosu

| Soru | Kısa Cevap |
|------|-------------|
| Mevcut mimariyle çizilebilirlik? | CNC: %85–98; mimari: %5–35 |
| Pipeline ölçeklenebilir mi? | Evet; preprocessing ile INSERT, ARC, SPLINE, filtre, cleanup eklenebilir |
| Preprocessing katmanı yeterli mi? | Evet; XREF/HATCH/DIM/TEXT hariç hedeflenen iyileştirmeler için yeterli |
| Tam CAD sınırı? | XREF, HATCH, DIMENSION, TEXT, 3D — desteklenmemeli |
| Üniversite kapsamı? | LINE, LWPOLYLINE, POLYLINE, ARC, CIRCLE, SPLINE, INSERT; katman filtreleme; deterministik pipeline |
| Roadmap? | Faz 1: ARC+CIRCLE+katman UI → Faz 2: SPLINE+INSERT+cleanup → Faz 3: HATCH/binary (opsiyonel) |

---

*Bu belge stratejik planlama amaçlıdır; kod değişikliği talimatı içermez.*
