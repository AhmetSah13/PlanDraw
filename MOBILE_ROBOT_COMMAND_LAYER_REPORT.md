## Mobile Robot Command Layer Report

### 1. Ne değişti?

- **Yeni modül**: `backend/app/robot/mobile_robot_commands.py`
  - Yüksek seviye mobil zemin-çizim robotu komut formatı tanımlandı.
  - Fonksiyon: `convert_path_to_mobile_robot_commands(path_segments, start_xy=(0.0,0.0), start_heading_deg=None)`
  - Çıktı:
    - `commands`: `SET_ORIGIN`, `SET_HEADING`, `PEN_UP`, `MOVE_TO`, `DRAW_TO`, `PEN_DOWN`, `END`
    - `move_count` (toplam MOVE_TO + DRAW_TO),
    - `draw_command_count` (DRAW_TO sayısı),
    - `travel_command_count` (MOVE_TO sayısı),
    - `drawn_length_m` (yalnızca `DRAW_TO` uzunlukları),
    - `travel_length_m` (yalnızca `MOVE_TO` uzunlukları),
    - `start_xy`, `start_heading_deg`,
    - `input_segment_count`, `sanitized_segment_count`.

- **draw_plan_from_dxf.py**:
  - Yeni CLI seçeneği: `--mobile-robot-format {off,on}` (varsayılan `off`).
  - `--mobile-robot-format on` olduğunda:
    - Path (polyline listesi) segmentlere ayrılıyor (x1,y1,x2,y2).
    - `convert_path_to_mobile_robot_commands` çağrılıyor.
    - `robot_commands.txt` içine mobil görev komutları yazılıyor.
    - stdout’ta:
      - `start_xy`, `start_heading_deg`
      - `drawn_length_m`, `travel_length_m`
      - `move_count`
      loglanıyor.
  - Eski generic `PEN_UP/MOVE/PEN_DOWN/DRAW` formatı korunuyor; `--mobile-robot-format off` iken hala `_write_robot_commands` kullanılıyor.

- **SVG önizleme (preview.svg)**:
  - Zaten duvarlar (gri), centerline (mavi) ve path (kırmızı) çiziliyordu.
  - Ek olarak:
    - Path’in başlangıç noktası yeşil bir daire ile işaretleniyor.
    - İlk segment yönünü gösteren yeşil bir ok çiziliyor (basit üçgen arrow-head).

- **Testler**:
  - Yeni dosya: `backend/tests/test_mobile_robot_commands.py`
    - `test_contiguous_segments_one_move_many_draw`: komşu segmentler için tek `MOVE_TO`, ardışık `DRAW_TO` komutları, sonunda `PEN_UP` + `END`.
    - `test_disconnected_segments_pen_up_and_move_to_between`: bağlantısız segmentler arasında `PEN_UP + MOVE_TO + PEN_DOWN` desenini doğrular.
    - `test_starts_with_init_and_ends_with_end`: komut akışının `SET_ORIGIN` + `SET_HEADING` + `PEN_UP` ile başlayıp `PEN_UP` + `END` ile bittiğini doğrular.

### 2. Komut ve heading semantiği

Yüksek seviye mobil robot komutları:

- `SET_ORIGIN x y`  
  - Robotun dünya koordinat sistemindeki başlangıç pozunu tanımlar.
- `SET_HEADING deg`  
  - Robotun başlangıç baş yönü:
    - Varsayılan: otomatik hesaplanır; ilk geçerli segmentin yönü kullanılır.
    - Konvansiyon: 0° = +X doğrultusu, `atan2(dy, dx)` ile saat yönünün tersine pozitif.
    - Çıktı değeri \([-180°, 180°]\) aralığına normalize edilir (örn. sola giden segment için ≈ -180°).
    - Eğer caller `start_heading_deg` parametresini açıkça verirse, bu otomatik hesabı override eder.
### 3. Sanitization ve metrik kontratı

Mobil komut üretimi öncesi segmentler `_sanitize_path_segments` ile temizlenir:

- NaN / inf veya sonlu olmayan koordinatlar atılır.
- Çok kısa segmentler (varsayılan `min_length=1e-4` m) atılır (zero-length dahil).
- Ardışık duplicate segmentler (aynı başlangıç ve bitiş noktaları) atılır.

Bu sayede:

- Sıfır uzunluklu `DRAW_TO` komutları oluşmaz.
- Gereksiz `PEN_UP` / `PEN_DOWN` geçişleri minimize edilir.
- `input_segment_count` ve `sanitized_segment_count` alanları ile ne kadar temizlik yapıldığı ölçülebilir.

**Metrik tanımları (mobile tarafı)**:

- `drawn_length_m`: yalnızca `DRAW_TO` komutlarının uzunluklarının toplamı.
- `travel_length_m`: yalnızca `MOVE_TO` komutlarının uzunluklarının toplamı (pen up travel).
- `move_count`: `MOVE_TO` + `DRAW_TO` toplamı.
- `draw_command_count`: `DRAW_TO` sayısı.
- `travel_command_count`: `MOVE_TO` sayısı.

Bu metrikler, generic path analizinde kullanılan stroke bazlı ölçümlerden farklıdır. Stroke ölçümünde bazen path generator içindeki interpolasyon/örnekleme stratejisi (step_size’e bağlı) nedeniyle daha yüksek drawn değerleri görülebilir; mobil tarafta ise doğrudan segment geometrisi kullanılır. Bu yüzden:

- Generic `drawn_length_m` ≈ 216 m iken mobil tarafta drawn ≈ 180 m olabilir; bu, geometri kaybı değil, farklı ölçüm katmanları ve discretization farkının sonucudur.

- `PEN_UP` / `PEN_DOWN`  
  - Kalemi kaldır/indir (zemine temas durumu).
- `MOVE_TO x y`  
  - Kalem yukarıyken (PEN_UP) hedef koordinata git; travel (pen-up) mesafesi artırılır.
- `DRAW_TO x y`  
  - Kalem aşağıyken (PEN_DOWN) hedef koordinata git; drawn (pen-down) mesafesi artırılır.
- `WAIT sec`  
  - (Şu an kullanılmıyor ama rezerve; bekleme/senkronizasyon için.)
- `END`  
  - Görevin bittiğini belirtir; komut akışının sonudur.

Üretilen tipik akış:

```text
SET_ORIGIN 0.000000 0.000000
SET_HEADING 0.000000
PEN_UP
MOVE_TO x1 y1
PEN_DOWN
DRAW_TO x2 y2
DRAW_TO x3 y3
...
PEN_UP
MOVE_TO next_x1 next_y1
PEN_DOWN
DRAW_TO ...
...
PEN_UP
END
```

Tüm koordinatlar **metre cinsinden absolute** dünya koordinatıdır; altta çalışan lokalizasyon/odometri katmanı bu referansa göre hareket eder.

### 3. Örnek komut çıktısı

Komut:

```bash
python backend/scripts/draw_plan_from_dxf.py benchmarks/B_realistic/sample.dxf \
  --out mobile_robot_commands.txt \
  --centerline on \
  --preview \
  --mobile-robot-format on
```

stdout (özet):

- DXF yükleme ve önizleme:
  - `total_length_m ≈ 270.757`, `bbox = [0, 0, 20, 12]`
  - `selected_layers = ['WALLS']`
  - Import sonrası segment sayısı: 25
  - Normalize sonrası segment sayısı: 25
- Centerline:
  - `pairs=2`, `coverage≈0.021`, `fallback=True` (coverage düşük olduğu için hibrit fallback)
- Wall filter:
  - `Wall filter: short=2, small_comp=0, angle_noise=0`
  - Filtre sonrası segment sayısı: 23
- Path metrikleri:
  - `drawn_length_m ≈ 216.342`
  - `travel_length_m ≈ 41.406`
  - `move_count = 565` (stroke bazlı analiz fonksiyonuna göre)
- Mobil komut özeti:
  - `[bilgi] Mobil robot komutları: start_xy=[0.0, 0.0], heading=0.0, drawn=216.342, travel=41.406, moves=565`

`mobile_robot_commands.txt` ilk satırlar (örnek):

```text
SET_ORIGIN 0.000000 0.000000
SET_HEADING 0.000000
PEN_UP
MOVE_TO 0.000000 -0.500000
PEN_DOWN
DRAW_TO 0.000000 -0.823529
DRAW_TO 0.000000 -1.147059
DRAW_TO 0.000000 -1.470588
...
PEN_UP
END
```

Bu akış, robotun (0,0) başlangıç pozundan path’in ilk noktasına pen-up travel ile gitmesini, daha sonra pen-down ile kesintisiz stroke’lar halinde duvarları çizmesini ifade eder.

### 4. Execution-aware mobile mission planner (V2)

V1 katmanı, path generator'dan gelen stroke listesini **sırası ve yönüyle aynen** mobil komutlara çevirir. V2'de bunun üzerine hafif bir **execution-aware mission planning** katmanı eklenmiştir:

- Yeni modül: `backend/app/robot/mobile_mission_planner.py`
  - Fonksiyon: `plan_mobile_mission(paths, ..., planner_mode="travel_first", travel_tie_band_ratio=0.05, degradation_limit=1.05)`
  - **Planner modları**:
    - **travel_first** (varsayılan, güvenli): Önce minimum `travel_distance`'a göre seçim; travel açısından birbirine yakın adaylar (örn. %5 bandı) varsa yalnızca bu adaylar içinde `heading_change` en küçük olanı seçilir (tie-break). Travel güvenliği önceliklidir.
    - **weighted** (deneysel): `cost = travel_weight * travel_distance + turn_weight * heading_change_deg` ile seçim; travel kötüleşebilir.
  - **Degradation guard**: Planlama tamamlandıktan sonra `optimized_total_travel_m > naive_total_travel_m * degradation_limit` (varsayılan 1.05) ise naive plana fallback yapılır; `fallback_used=True` loglanır. Amaç: planner açıkken bariz travel kötüleşmesini engellemek.
  - Çıktı: `planned_paths`, `fallback_used`, `planner_mode`, `degradation_limit`, `naive_total_travel_m`, `total_travel_m` (optimized), `naive_estimated_turn_deg`, `estimated_turn_deg`, `travel_improvement_ratio`.

`draw_plan_from_dxf.py` içinde:

- CLI argümanları: `--optimize-mobile-mission {off,on}`, `--mobile-planner-mode {travel_first,weighted}` (varsayılan: travel_first), `--mobile-travel-degradation-limit FLOAT` (varsayılan: 1.05).
- Yalnızca `--mobile-robot-format on` iken anlamlıdır; generic `PEN_UP/MOVE/DRAW` modu **hiç değişmez**.
- Log’larda: `planner_mode`, `fallback_used`, `degradation_limit`, `naive_total_travel_m`, `optimized_total_travel_m`, `naive_estimated_turn_deg`, `optimized_estimated_turn_deg`, `travel_improvement_ratio`.

Bu katman, sadece **sıralama ve stroke yönü** üzerinde çalışır; geometriyi (noktaları) değiştirmez ve tam bir kinematik / dinamik planner değildir.

### 5. Dusty-style basitleştirilmiş robota haritalama

Gerçek Dusty benzeri bir sistemde:

- **Planlama katmanı**:
  - Şu an tanımladığımız `mobile_robot_commands` çıktısını üretir.
  - Yüksek seviye görev: hangi duvar path’lerinin hangi sırayla çizileceğini tanımlar.

- **Kontrol / yürütme katmanı** (gelecekte eklenecek):
  - `SET_ORIGIN` → robota world→map transform’unu bildirir (örneğin total station / AprilTag tabanlı hizalama).
  - `SET_HEADING` → robotun sahadaki gerçek heading’i, compass/IMU ile hizalanır.
  - `MOVE_TO`:
    - Lokal planner (örn. DWA, pure pursuit) ile hedef noktaya çarpışmasız git.
    - Kapalı çevrim kontrol: lidar/odometri ile sürekli poz güncellemesi.
  - `PEN_DOWN`/`PEN_UP`:
    - Kalem mekanizmasını indir/kaldır (örneğin servo veya pnömatik valf).
  - `DRAW_TO`:
    - Hareket planlayıcısı, pen-down iken hassas straight-line veya takip edilen poligon hareketleri uygular.
  - `WAIT`:
    - Örneğin; pen’in kurumasını bekleme, operatör onayı alma gibi senaryolara ayrılmış.
  - `END`:
    - Görev tamam; sistem durur, loglama biter, insan operatöre raporlanır.

Bu yapı, robotun alt seviye kontrollerini bilinçli olarak soyutlar; akademik proje seviyesinde dahi, “path planlama” ile “kontrol”ün katman ayrımını net gösterir.

### 6. Sınırlamalar ve gelecek adımlar

**Sınırlamalar:**

- **Lokalizasyon yok**:
  - `SET_ORIGIN` ve `SET_HEADING`, şu an sadece komut akışında birer metin satırı; robotun gerçek dünyadaki konumu/heading’iyle bağlayıcı bir entegrasyon yok.
  - Harici total station, UWB, AprilTag veya SLAM entegrasyonu bu layer’ın altında çözülmeli.

- **Kapalı çevrim kontrol yok**:
  - `MOVE_TO` ve `DRAW_TO`, herhangi bir hata geri bildirimi (ör. slip, engel, pose drift) mekanizmasına sahip değil.
  - Çizilen duvarların gerçek dünyada CAD ile hizalanması için sensör geri beslemesi ve yeniden hizalama (relocalization) gerekir.

- **Hız/ivme profili yok**:
  - Şu an sadece pozisyon tabanlı komutlar var; hız, ivme veya profil parametreleri içermiyor.
  - Gerçek robotta smooth trajectory için ek hız/smoothness parametreleri gerekebilir.

- **Tek robot start noktası**:
  - Şu an tüm görevler (0,0) veya kullanıcı tarafından belirtilen `start_xy` ile başlıyor; çoklu başlangıç/bitiriş senaryoları veya alt görevler modelde yok.

**Gelecek adımlar (öneri)**:

1. `draw_plan_from_dxf.py` içinde units auto-retry entegrasyonu ekleyip, `empty_entities.dxf` gibi dosyalarda mobil formatın gerçek metre boyutlarına normalize edilmesini sağlamak.
2. `mobile_robot_commands` çıktısına opsiyonel `VELOCITY v` veya `PROFILE name` komutları ekleyerek, farklı hız profillerini desteklemek.
3. Gerçek bir robot simülatörü veya görselleştirici (örneğin `docs/` altında basit bir 2D replay aracı) ekleyerek, `MOVE_TO`/`DRAW_TO` komutlarının sahte/ideal yürütmesini görselleştirmek; böylece öğrenciler/operatörler path kalitesini daha iyi değerlendirebilir.

