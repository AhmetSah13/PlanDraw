## MVP Internet DXF Duvar-Only Kanıt Raporu

### A) Özet (Executive summary)

- **Toplam test edilen dosya**: 6 (A_expected_pass: 4, B_realistic: 2)
- **Sonuç dağılımı (ALL_run)**: PASS=6, WARN=0, FAIL=0
- **Scope kırılımı (ALL_run)**: in_scope_total=3 (SUPPORTED_WALL_ONLY), out_scope_total=3 (OUT_OF_SCOPE_OTHER)
- **Yanıt**: **Robot, MVP tanımına göre “internet DXF’leri”ni duvar-only seviyesinde çizebilir**, ancak bu ifade yalnızca `SUPPORTED_WALL_ONLY` scope’una giren planlar için geçerlidir (duvar katmanları net, units makul, annotation/block karmaşıklığı düşük). OUT_OF_SCOPE planlar için sistem bilinçli şekilde “kapsam dışı” raporlamakta, çizimi zorlamamaktadır.

---

### B) Sonuç tabloları (per suite)

#### 1) Suite A (`A_run`, centerline=off)

- **PASS/WARN/FAIL**:
  - PASS=4, WARN=0, FAIL=0
- **Scope**:
  - in_scope_total=3 (SUPPORTED_WALL_ONLY)
  - out_scope_total=1 (`OUT_OF_SCOPE_OTHER`)
  - out_scope_by_class: `OUT_OF_SCOPE_OTHER`=1
- **Metrik medyanları (summary.json)**:
  - **median shape_retention_drawn** (by_suite.A) = 1.0
  - **in_scope_median_retention_vs_walls_candidate** = 1.0
  - **in_scope_median_path_overhead** ≈ 1.0045

Yorum: A seti (sentetik double-wall duvar planları) için hem geometri tutulumu hem de path_overhead mükemmele çok yakın; robot, “temiz” planlarda duvar-only centerline davranışını deterministik şekilde sağlıyor.

#### 2) Suite B (`B_run`, centerline=on)

- **PASS/WARN/FAIL**:
  - PASS=2, WARN=0, FAIL=0
- **Scope**:
  - in_scope_total=2 (her iki dosya da SUPPORTED_WALL_ONLY)
  - out_scope_total=0
- **Metrik medyanları (summary.json)**:
  - **median shape_retention_drawn** (by_suite.B) ≈ 0.6498  
  - **in_scope_median_retention_vs_walls_candidate** ≈ 0.9997
  - **in_scope_median_path_overhead** ≈ 1.2317

Yorum: B seti (daha gerçekçi planlar) için, duvar layer’ı üzerindeki duvar uzunluğunun neredeyse tamamı korunuyor (`retention_vs_walls_candidate` ≈ 1.0), ancak path_overhead ≈ 1.23 seviyesinde; yani pen-up travel hâlâ anlamlı fakat kabul edilebilir bir ek maliyetle var.

#### 3) Tüm suite’ler (`ALL_run`, centerline=on)

- **PASS/WARN/FAIL (ALL_run)**:
  - PASS=6, WARN=0, FAIL=0
- **Scope**:
  - in_scope_total=3
  - out_scope_total=3
  - out_scope_by_class: `OUT_OF_SCOPE_OTHER`=3
- **İn-scope metrik medyanları (ALL_run)**:
  - **in_scope_median_retention_vs_walls_candidate** = 1.0
  - **in_scope_median_path_overhead** ≈ 1.2362

Yorum: Tüm dosyalar başarıyla çizilebilir (PASS), fakat scope sınıflandırıcısı, mimari anlamda “MVP duvar-only” hedefi dışında kalan 3 dosyayı `OUT_OF_SCOPE_OTHER` altında topluyor. İn-scope üç dosyada hem duvar uzunluğu tutulumu 1.0, hem de path_overhead düşük/orta seviyede.

---

### C) Root cause kartları (yalnızca FAIL / WARN / OUT_OF_SCOPE)

Bu koşul setinde **hiç FAIL veya WARN yoktur**. Root cause kartları, **OUT_OF_SCOPE** (kapsam dışı) olan dosyalar için üretilmiştir. Eldeki per-dosya JSON’lar üzerinden deterministik olarak yalnızca aşağıdaki dosya out-of-scope olarak gözlemlenmiştir:

#### 1) `benchmarks/A_expected_pass/double_wall_T_junction.dxf`

- **Genel**:
  - **Suite**: A
  - **Final result**: PASS
  - **scope_class**: `OUT_OF_SCOPE_OTHER`

- **Units / bbox**:
  - **dxf_units_detected**: `"mm"`
  - **units_retry_used**: `false`
  - **units_candidates**: `null`
  - **units_chosen**: `null`
  - **bbox_size**: `[6.0 m, 8.0 m]` (makul mimari plan boyutu)

- **Layer seçimi / graph skoru**:
  - **selected_layers**: `["WALLS"]`
  - **layer_intelligence.scores**:
    - `WALLS`: 8.3673
  - **Top-1 layer_graph_scores**:
    1. `WALLS`: score ≈ 7.0509  
       - total_length_m = 28.0  
       - edge_count = 4  
       - dangling_edges_count = 4  
       - closed_cycles_count = 0  
       - dominant_angles: {0°: 2, 90°: 2, other: 0}

- **Entity mix (dxf_diagnostics.entity_counts)**:
  - LINE: 4
  - LWPOLYLINE: 0
  - POLYLINE: 0
  - ARC: 0
  - SPLINE: 0
  - HATCH: 0
  - INSERT: 0
  - TEXT: 0
  - DIMENSION: 0

- **Temel path metrikleri**:
  - **drawn_length_m**: 28.0
  - **travel_length_m**: ≈ 3.8986
  - **path_overhead**: ≈ 1.1392
  - **move_count**: 567

- **Centerline**:
  - Bu koşu `A_run` içinde, `--centerline off` ile yapılmıştır; centerline alanları bu raporda **yoktur**.
  - Centerline fallback / coverage bu koşu için **uygulanmamıştır**.

- **Wall filter**:
  - **wall_filter_decision.used**: `true`
  - **reason**: `"FILTER_OK"`
  - **wall_candidate_length_m**: 28.0
  - **wall_final_length_m**: 28.0
  - **wall_filter_metrics_before/after**: drawn/travel/path_overhead/move_count birebir aynıdır → filtre geometriyi bozmaz.

- **Muhtemel kök neden (OUT_OF_SCOPE_OTHER)**:
  - Geometri ve metrikler duvar-only açısından kusursuz (retention vs walls candidate = 1.0, path_overhead ≈ 1.14, wall_likeliness_score ≈ 0.37), ancak **scope sınıflandırıcısının pozitif kriterlerini karşılamaz**:
    - `graph_metrics.wall_likeliness_score` yalnızca ≈ 0.37 (SUPPORTED_WALL_ONLY eşiği 0.6 civarında),
    - Çok basit, az sayıda kenarlı T-junction geometrisi, “oda benzeri” kapalı kontur ve güçlü duvar grafı kriterlerini tam sağlayamaz.
  - Bu nedenle dosya teknik olarak PASS olsa da heuristik olarak **MVP duvar-only hedefinin anlamlı bir internet planı** olmadığı için `OUT_OF_SCOPE_OTHER` sınıfına düşmektedir.

- **recommended_actions** (rapordaki hazır öneriler):
  - `Bu plan şimdilik MVP kapsamı dışında; duvar-only sadeleştirilmiş bir DXF üretip tekrar deneyin.`
  - `Duvar layer'larını netleştirip (örneğin WALL/A-WALL) diğer layer'ları export sırasında kapatmayı deneyin.`

---

### D) Kanıta dayalı, öncelikli 3 sonraki adım

Bu adımlar tamamen **mevcut ölçümler ve raporlar** üzerinden çıkarılmıştır; yeni özellik “icat edilmemiş”, yalnızca gözlenen boşluklar sıralanmıştır.

1. **Scope sınıflandırıcısını sentetik testleri cezalandırmayacak şekilde ayarlamak**  
   Kanıt: `double_wall_T_junction.dxf` dosyası, geometri ve path açısından kusursuz olmasına rağmen `OUT_OF_SCOPE_OTHER` altında raporlanıyor. Bu, gerçek internet planı olmayan sentetik dosyalarda gereksiz “kapsam dışı” etiketi üretip metrikleri bozuyor.  
   Aksiyon: Scope kurallarında, çok küçük / oyuncak sentetik planları (az entity, kısa toplam uzunluk, tek layer, units sağlam) SUPPORTED_WALL_ONLY veya “test fixture” gibi özel bir sınıfa almak; böylece gerçek internet DXF’leri için scope istatistikleri daha temiz olur.

2. **B_realistic setindeki path_overhead’i daha sistematik analiz etmek**  
   Kanıt: Suite B için in-scope median `retention_vs_walls_candidate` ≈ 1.0 iken in-scope median `path_overhead` ≈ 1.23 seviyesinde. Yani duvar geometri kaybı neredeyse yok, ancak pen-up travel hâlâ anlamlı bir paya sahip.  
   Aksiyon: Mevcut ScenarioLimits’i değiştirmeden, B setindeki dosyalar için pen-up travel dağılımını (özellikle uzun boş geçişler) raporlayıp; hangi duvar bileşenleri arasında gereksiz atlamaların kaldığını belirlemek (örneğin bileşen sıralama / traversal stratejilerini yalnızca ölçümsel olarak yeniden değerlendirmek).

3. **Gerçek internet DXF koleksiyonu ile kapsam ve başarı oranını genişletmek**  
   Kanıt: Mevcut benchmarklar (A_expected_pass ve B_realistic) sınırlı sayıdadır (toplam 6 dosya). Scope metrikleri ve PASS oranları bu kümeye göre çok iyi görünse de, “internet DXF’leri” uzayının sadece çok küçük bir alt kümesi ölçülmüştür.  
   Aksiyon: En az 10–20 gerçek internet DXF örneğini toplayıp `verify_dxf_drawability.py` ile ALL_run benzeri bir koşu daha almak; özellikle:
   - scope_class dağılımı (SUPPORTED_WALL_ONLY vs OUT_OF_SCOPE_*),
   - in_scope median `retention_vs_walls_candidate`,
   - in_scope median `path_overhead`  
   metriklerini yeniden raporlayarak, mevcut heuristiklerin gerçek dünyada nerede yetersiz kaldığını kanıta dayalı olarak görmek.

