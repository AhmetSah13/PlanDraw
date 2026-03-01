# Plan Pipeline Analizi: Riskler ve Sağlamlaştırma Önerileri

Bu belge, DXF/DWG/JSON/Manual plan yüklemesi sonrası **parse → normalize → plan → path → commands → analyze → simulate** pipeline'ını uçtan uca inceleyip varsayımlar, edge-case'ler ve önerilen korumaları listeler.

---

## 1) Pipeline adımları ve varsayımlar / edge-case'ler

### 1.1 Import (import_dxf / import_dwg / import_plan)

| Adım | Varsayımlar | Edge-case / sessiz geçiş | ok=false gerekirken ilerleme? |
|------|-------------|---------------------------|------------------------------|
| **DXF** `dxf_to_normalized_plan` | Dosya ASCII/UTF-8; ENTITIES var; en az bir LINE/LWPOLYLINE/POLYLINE. | Binary DXF → UTF-8 decode hatası, doğru dönüyor. | Hayır; segment yoksa ValueError. |
| **DWG** | Converter yapılandırılmış; çıktı UTF-8 DXF. | Converter ANSI/CP1254 verirse UTF-8 strict ile red. | Hayır. |
| **JSON** `import_plan_from_json` | `segments` dolu; units mm/cm/m. | `segments` boş → ValueError. | Hayır. |
| **Manual** | Kullanıcı LINE metni yazar; compile_plan ile işlenir. | Boş veya geçersiz satırlar parse'da hata. | compile_plan ayrı endpoint; import değil. |

- **Ortak risk:** Tüm import'larda `options` (step_size, speed) sınırsız büyük/küçük olabilir; backend `max(0.01, step_size)` ile sınırlı, aşırı değerler hâlâ garip path/komut üretebilir (uyarı yeterli olabilir).

### 1.2 normalize_plan

| Adım | Varsayımlar | Edge-case | ok=false gerekirken? |
|------|-------------|-----------|----------------------|
| Zero-length drop | `merge_endpoints_tol` makul (1e-6). | Tüm segmentler sıfır uzunlukta → ValueError. | Hayır; zaten ValueError. |
| Collinear merge | Ardışık segmentler uç paylaşıyor; max_merges=1000. | 1000+ merge gerekirse döngü erken kesilir; birleşmemiş segmentler kalır (warning yok). | Warning eklenebilir; ok=false zorunlu değil. |
| Çıktı | `segments` en az 1 eleman. | Normalizer "segment kalmadı" diye ValueError atıyor. | Hayır. |

- **Sessiz risk:** Normalize sonrası tek segment kalıp o da çok küçük (örn. 1e-10 uzunluk) olabilir; bir sonraki adımda path noktaları aşırı sık veya tek nokta olur; kullanıcı "bir şey olmadı" diyebilir.

### 1.3 normalized_to_plan / normalized_to_walls_array / normalized_to_plan_text

| Adım | Varsayımlar | Edge-case | ok=false? |
|------|-------------|-----------|-----------|
| Segment → Wall / plan_text / walls | NormalizedPlan.segments en az 1; koordinatlar float. | NaN/Inf segment'te yok (Pydantic sayısal). | Yok. |
| normalized_to_plan(Plan) | Plan.walls boş olabilir mi? → normalized.segments boş olamaz (min_length=1). | — | Hayır. |

- **Risk:** NormalizedPlan'da `min_length=1` var; normalize sonrası boş liste ile NormalizedPlan üretilmiyor (ValueError). Yani bu katmanda boş plan çıkmaz.

### 1.4 PathGenerator

| Adım | Varsayımlar | Edge-case | ok=false? |
|------|-------------|-----------|-----------|
| step_size > 0 | main'de max(0.01, step_size). | step_size çok büyükse duvar başına 1–2 nokta; path çok kısa. | Warning yeterli. |
| Duvar uzunluğu 0 | plan_module.Wall (x1,y1)-(x2,y2) aynı nokta. | _generate_points_for_wall tek nokta döner; path boş değil ama anlamsız. | Normalize zero-length drop ile bu duvar olmamalı. |
| Plan boş (walls=[]) | PathGenerator plan.walls üzerinde iterate. | generate_path() = []; compile_path_to_commands boş path ile SPEED + PEN UP döner. | Import tarafında normalized en az 1 segment garantili; boş plan sadece başka bir hata sonucu olur. |

- **Sessiz risk:** Path tek nokta veya çok az nokta; script üretilir ama W2'de "hiç çizgi yok" hissi. Invariant: path length veya move sayısı 0 ise uyarı/ok=false düşünülebilir.

### 1.5 compile_path_to_commands / serialize_commands

| Adım | Varsayımlar | Edge-case | ok=false? |
|------|-------------|-----------|-----------|
| path boş | SPEED + PEN UP döner. | commands_text kısa; analyze/simulate çalışır ama çizim yok. | Kullanıcıya "plan çizilebilir değil" demek için ok=false veya warning mantıklı. |
| Ardışık aynı nokta | Atlanıyor. | Path çok uzun, tekrarlı noktalar → komut sayısı azalır; beklenen davranış. | Hayır. |

### 1.6 analyze / simulate

| Adım | Varsayımlar | Edge-case | ok=false? |
|------|-------------|-----------|-----------|
| commands_text | Parse strict=False; hata varsa parser_diags. | Boş script → commands=[], blocked parser'a bağlı. | API ayrı; import değil. |
| walls | Opsiyonel; collision için kullanılır. | Frontend analyze/simulate'e walls gönderiyor mu? Gönderiyorsa walls ile path uyumsuzluğu (farklı step_size ile üretilmiş path) teorik. | Tutarlılık frontend'de aynı state'ten gelince sağlanır. |
| Export / Simulate | Analyze edilmeden çağrılabilir. | Kullanıcı W2'de Çiz veya Export'a basar; analyze hiç çalışmamış olabilir. | UX: "Önce Analiz et" uyarısı; backend zorunlu bloklamak gerekmez. |

- **Risk:** Analyze edilmeden simulate/export yapılabilmesi; kullanıcı güvenli mi bilmeden ilerleyebilir. Bu daha çok frontend akışı ve uyarı ile çözülür.

---

## 2) Dosya formatından bağımsız ortak riskler

| Risk | Açıklama | Öneri |
|------|----------|--------|
| **Normalize sonrası boş segment** | Zaten normalize_plan ValueError atıyor; ancak "tek segment kaldı, uzunluk ~0" (EPS sınırında) durumu var. | Normalize sonrası min segment uzunluğu kontrolü (örn. toplam path length veya en kısa segment > eşik). |
| **Çok küçük segmentler / precision** | EPS=1e-12; sayısal gürültü ile çok küçük segmentler birleşmeyebilir veya path'te anlamsız noktalar. | Warning: "Plan çok küçük segmentler içeriyor; sonuç hassasiyet nedeniyle farklı olabilir." |
| **scale / units / origin tutarsızlığı** | DXF'te units override + scale override birlikte; JSON'da origin. Import'lar arası aynı plan farklı birimde açılırsa farklı boyut. | Dokümantasyon / UI'da birim bilgisi; backend ek tutarsızlık kontrolü zorunlu değil. |
| **Path boş ama script üretilmesi** | Normalized en az 1 segment olsa bile, normalize sonrası hepsi düşerse ValueError. Ama path = [] (plan.walls boş) teorik olarak başka bir bug'dan kalabilir. | Import pipeline'da normalize sonrası segment sayısı > 0 ve path üretildikten sonra path length kontrolü. |
| **Walls ile path uyumsuzluğu** | walls = normalized_to_walls_array(normalized); path = PathGenerator(normalized_to_plan(normalized), step_size).generate_path(). Aynı normalized'dan geldiği için uyumlu. | Frontend'de tek state; ek kontrol gerekmez. |
| **Analyze edilmeden simulate/export** | İşlevsel olarak mümkün; kullanıcı hataya açık. | Frontend: W2/W6'da "Önce Analiz önerilir" veya analyze otomatik tetikleme. |

---

## 3) Backend’de eklenmesi gereken koruma kontrolleri

### 3.1 ValueError → ok=false

- **Zaten var:** import_plan_from_json (segments boş), dxf_to_normalized_plan (segment yok), normalize_plan (segment kalmadı), PathGenerator (step_size <= 0).
- **Önerilen ek:**  
  - **Import pipeline sonunda (import_dxf / import_dwg / import_plan):** Path üretildikten sonra `len(raw_path) == 0` ise `ok=false` + "Plan çizilebilir nokta üretmedi; segmentleri kontrol edin."  
  - **Normalize sonrası:** `len(normalized.segments) == 0` → zaten normalize_plan ValueError atıyor; ekstra guard gerekmez.  
  - **Invariant check:** Normalize sonrası tüm segmentlerin uzunluğu < min_segment_length (örn. 1e-6) ise uyarı veya ok=false (tercih: warning + devam).

### 3.2 Warning yeterli olanlar

- Collinear merge sayısı max_merges'a ulaştı.
- Toplam path noktası çok yüksek (performans uyarısı).
- step_size veya speed kullanıcı tarafından aşırı ayarlandı (sınırlar dışında kalan değerler clamp edilip warning).

### 3.3 Normalize sonrası invariant

- `len(segments) >= 1` (zaten normalize ValueError atıyor).
- İsteğe bağlı: Tüm segmentler için `hypot(x2-x1, y2-y1) >= merge_endpoints_tol` (zero-length kalmamalı). İhlal varsa warning.
- Path aşamasında: `len(path) >= 2` veya en az bir MOVE içeren commands; aksi halde ok=false (veya net warning).

---

## 4) Frontend UX sorunlu noktaları

| Sorun | Açıklama | Öneri |
|-------|----------|--------|
| **Teknik / anlamsız hata metni** | Backend'den gelen "segments boş olamaz", "DXF dosyasında desteklenen entity bulunamadı" gibi mesajlar kullanıcıya ham gösteriliyor. | Hata kategorisi: "Dosya formatı / içerik" vs "Plan çizilemiyor". Format/entity için kısa özet + "Detay: {backend mesajı}". |
| **"Format bozuk" vs "Plan çizilemez"** | Format: DXF binary, JSON schema hatası, ENTITIES yok. Plan çizilemez: segment yok, normalize sonrası boş, path boş. | Backend error mesajlarında anahtar kelime veya kod; frontend'de "Dosya açılamadı" / "Plan çizilebilir içerik yok" ayrımı. |
| **Import başarılı görünüp W2/W1'de hiçbir şey olmaması** | Path tek nokta veya script sadece SPEED+PEN UP; W2'de çizgi yok. | Backend path/command boşsa ok=false yaparak engellemek; veya frontend'de "Plan çizilebilir nokta yok" uyarısı. |
| **Failed to fetch** | "Backend'e ulaşılamadı" metni var; bazı yerlerde "Backend çalışıyor mu? (http://127.0.0.1:8000)" ekli. | Tüm import hatalarında aynı ağ hatası mesajı (backend URL ile). |

---

## 5) Uygulanan patch’ler (özet)

- **Backend guard (main.py):** `import_dxf`, `import_dwg`, `import_plan` içinde path üretildikten sonra `raw_path` boşsa `ok=false` ve hata: *"Plan çizilebilir nokta üretmedi; segmentleri veya step_size değerini kontrol edin."*
- **Normalize sonrası kontrol (plan_normalizer.py):** Collinear merge sonrası, kalan segmentlerden herhangi birinin uzunluğu `merge_endpoints_tol` altındaysa uyarı: *"Çok küçük segment kaldı; sonuçlar hassasiyet nedeniyle farklı olabilir."*
- **Frontend hata mesajı (App.jsx):** `formatImportError(backendError, isNetworkError)` eklendi; ağ hatasında tek mesaj, dosya/format hatalarında "Dosya formatı veya içerik uygun değil. Detay: ...", plan/segment/path hatalarında "Plan çizilemiyor: ..." kullanılıyor. DXF/DWG/JSON import hata ve catch bloklarında kullanılıyor.
