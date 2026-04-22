# PlanDraw — Gerçek DXF Desteği Uygulama Planı

**Tarih:** 2025-02-27  
**Hedef:** ARC, CIRCLE, LWPOLYLINE(bulge), SPLINE, INSERT desteği ile mimari/CNC/dekoratif DXF'lerde kontur geometrisini çizilebilir segmente çevirmek.

---

## 1. ezdxf vs Manuel Parser Karşılaştırması

| Kriter | ezdxf | Manuel (mevcut parser) |
|--------|-------|------------------------|
| **ARC/CIRCLE** | `make_path()` + `flattening(distance)` — hazır | Group 10,20,40,50,51 parse + chord hesabı — ~50 satır |
| **LWPOLYLINE bulge** | `make_path()` otomatik | Bulge→arc dönüşümü (bulge = tan(θ/4)) — ~80 satır |
| **SPLINE/NURBS** | `make_path()` + `add_spline()` — knot/weight/degree otomatik | NURBS evaluator — 200+ satır, hata riski yüksek |
| **INSERT/BLOCKS** | `doc.blocks`, `entity.virtual_entities()` — transform hazır | BLOCKS section parse + recursive + 2D affine — 150+ satır |
| **Binary DXF** | Otomatik | Destek yok |
| **Bağımlılık** | `ezdxf>=1.4.0` (~2 MB) | Yok |
| **Bakım** | ezdxf topluluk | Kendi kodumuz |
| **Test kapsamı** | ezdxf kendi testleri | Sıfırdan |

**Öneri: ezdxf kullan.** SPLINE ve INSERT elle yazmak çok zaman ve bug demek. ezdxf MIT lisanslı, aktif geliştiriliyor, `make_path()` + `flattening()` tam ihtiyacımızı karşılıyor.

---

## 2. Mimari Özet

```
Raw DXF (ASCII/Binary)
    ↓
ezdxf.readfile() veya mevcut parse_dxf_ascii (geçiş dönemi)
    ↓
┌─────────────────────────────────────────────────────────────────┐
│  dxf_preprocess.py                                               │
│  1. load_dxf() → ezdxf.Document veya fallback raw parse          │
│  2. explode_inserts() → BLOCKS patlat, 2D affine transform       │
│  3. discretize_curves() → ARC/CIRCLE/SPLINE/bulge → chord chain  │
│  4. entities_to_segments() → SegmentIn[] (metre)                  │
└─────────────────────────────────────────────────────────────────┘
    ↓
dxf_to_normalized_plan (mevcut) — artık preprocess çıktısını kullanır
    ↓
normalize_plan → PathGenerator → scenario_analysis → export (değişmez)
```

---

## 3. Dosya Bazlı Değişiklikler

### Yeni dosyalar

| Dosya | İçerik |
|-------|--------|
| `backend/app/importers/dxf_preprocess.py` | `DiscretizeConfig`, `explode_inserts()`, `discretize_curves()`, `entities_to_segments()`, `load_dxf_with_ezdxf()` |
| `backend/app/importers/dxf_ezdxf_adapter.py` | ezdxf → SegmentIn köprü; `ezdxf_doc_to_segments(doc, cfg)` |
| `backend/golden_dxfs/arc_circle_demo.dxf` | ARC + CIRCLE içeren minimal ASCII DXF |
| `backend/golden_dxfs/spline_logo_demo.dxf` | SPLINE içeren minimal DXF |
| `backend/golden_dxfs/insert_block_demo.dxf` | INSERT + BLOCKS içeren minimal DXF |

### Güncellenecek dosyalar

| Dosya | Değişiklik |
|-------|------------|
| `backend/requirements.txt` | `ezdxf>=1.4.0` ekle |
| `backend/pyproject.toml` | `dependencies` (varsa) güncelle |
| `backend/app/importers/dxf_importer.py` | `dxf_to_normalized_plan` → preprocess çağrısı; "supported yok" kontrolü preprocess sonrası; `inspect_dxf_layers` → ezdxf veya mevcut parse ile entity sayımı güncelle |
| `backend/app/importers/__init__.py` | `dxf_preprocess` export |
| `backend/app/api/schemas.py` | `ImportDxfOptions` → `chord_tolerance`, `explode_blocks`, `max_insert_depth` (opsiyonel) |
| `backend/scripts/verify_dxf_drawability.py` | entity_counts_supported artışını doğrula |

### Test dosyaları

| Dosya | İçerik |
|-------|--------|
| `backend/tests/test_arc_discretization.py` | ARC chord tolerance, max segment length |
| `backend/tests/test_circle_discretization.py` | CIRCLE kapalı döngü |
| `backend/tests/test_lwpolyline_bulge.py` | LWPOLYLINE bulge→segment |
| `backend/tests/test_spline_discretization.py` | SPLINE deterministik nokta sayısı |
| `backend/tests/test_insert_explode.py` | INSERT transform, recursive depth |
| `backend/tests/test_dxf_preprocess_integration.py` | Golden DXF'lerle uçtan uca |

---

## 4. PR Boyutunda Roadmap

### PR-1: Bağımlılık + Discretization Altyapısı (1–2 gün)
- `requirements.txt`: ezdxf>=1.4.0
- `dxf_preprocess.py`: `DiscretizeConfig`, `chord_tolerance` hesaplama (adaptif)
- `dxf_ezdxf_adapter.py`: `ezdxf_doc_to_segments()` — sadece LINE/LWPOLYLINE(bulge=0)/POLYLINE ile mevcut davranışı doğrula
- Test: mevcut DXF'ler aynı sonucu vermeli (regresyon yok)

### PR-2: ARC + CIRCLE Discretization (1 gün)
- `discretize_curves()`: ARC, CIRCLE → `make_path()` + `flattening(distance)`
- `golden_dxfs/arc_circle_demo.dxf` oluştur
- Test: `test_arc_discretization_produces_expected_length_and_max_chord`, `test_circle_discretization_closes_loop`

### PR-3: LWPOLYLINE Bulge (1 gün)
- ezdxf `make_path()` LWPOLYLINE bulge'u zaten destekliyor
- Test: `test_lwpolyline_bulge_discretization_basic`

### PR-4: SPLINE Discretization (1–2 gün)
- ezdxf `make_path(entity, segments=N)` veya `flattening(distance)`
- `golden_dxfs/spline_logo_demo.dxf`
- Test: `test_spline_discretization_reasonable_point_count`

### PR-5: INSERT Explode (2–3 gün)
- BLOCKS parse (ezdxf `doc.blocks` veya mevcut parser ile BLOCKS section)
- `explode_inserts()`: insertion point, rotation, scale_x/y, recursive depth
- `golden_dxfs/insert_block_demo.dxf`
- Test: `test_insert_explode_simple_block`, `test_recursive_insert_depth_limit`

### PR-6: Insight + Uyarı Güncellemeleri (1 gün)
- `entity_counts_supported` → ARC/CIRCLE/SPLINE "supported_via_discretize" (geriye uyumlu)
- Yeni uyarılar: `SPLINE_DISCRETIZED`, `ARC_DISCRETIZED`, `INSERT_EXPLODED`, `INSERT_TOO_DEEP`, `NONUNIFORM_SCALE`
- `recommended_action`: "SPLINE segmente çevrildi (N segment)"

### PR-7: Entegrasyon + Verify (1 gün)
- `dxf_to_normalized_plan`: ezdxf path; "supported yok" preprocess sonrası
- `verify_dxf_drawability.py`: entity_counts_supported, PASS/WARN
- Mevcut API sözleşmeleri korunmalı

---

## 5. dxf_preprocess Modül Yapısı (Net)

```
backend/app/importers/
├── dxf_importer.py      # Ana giriş; dxf_to_normalized_plan, inspect_dxf_layers
├── dxf_preprocess.py    # YENİ: discretize, explode, config
├── dxf_ezdxf_adapter.py # YENİ: ezdxf → SegmentIn köprü
└── ...
```

### dxf_preprocess.py Fonksiyonları

```python
# Config
@dataclass
class DiscretizeConfig:
    chord_tolerance: float
    max_segment_length: float | None
    max_insert_depth: int = 8
    explode_blocks: bool = True

def adaptive_chord_tolerance(bbox: list[float] | None) -> float: ...

# Ana pipeline (ezdxf kullanıyorsa)
def load_dxf_with_ezdxf(path_or_text) -> ezdxf.Document | None: ...

def explode_inserts(
    doc: ezdxf.Document,
    cfg: DiscretizeConfig,
) -> list[ezdxf.DXFEntity]: ...

def discretize_curves(
    entities: list,
    cfg: DiscretizeConfig,
    scale: float,
    origin: tuple[float, float],
) -> list[SegmentIn]: ...

def entities_to_segments(
    doc_or_entities,
    cfg: DiscretizeConfig,
    scale: float,
    origin: tuple[float, float],
    layer_whitelist: list[str] | None,
    layer_blacklist: list[str] | None,
) -> tuple[list[SegmentIn], dict]:  # (segments, stats)
```

### dxf_ezdxf_adapter.py

```python
def ezdxf_doc_to_segments(
    doc: ezdxf.Document,
    cfg: DiscretizeConfig,
    scale: float,
    origin: tuple[float, float],
    layer_whitelist: list[str] | None = None,
    layer_blacklist: list[str] | None = None,
) -> tuple[list[SegmentIn], dict]: ...
```

### dxf_importer.py Değişiklikleri

- `dxf_to_normalized_plan()`:
  1. ezdxf varsa: `ezdxf_doc_to_segments()` çağır
  2. Yoksa: mevcut parse + sadece LINE/LWPOLYLINE(bulge=0)/POLYLINE
  3. "Supported entity yok" kontrolü: preprocess/import sonrası segment listesi boşsa
- `inspect_dxf_layers()`: ezdxf ile entity sayımı (ARC/CIRCLE/SPLINE/INSERT dahil) veya mevcut `_count_all_entities_and_unsupported_samples` güncelle

---

## 6. Uygulama Detayları

### 6.1 DiscretizeConfig

```python
@dataclass
class DiscretizeConfig:
    chord_tolerance: float  # metre; max chord–arc sapma
    max_segment_length: float | None  # metre; opsiyonel üst sınır
    max_insert_depth: int = 8
    explode_blocks: bool = True
```

**Adaptif tolerance:**
```python
def _adaptive_chord_tolerance(bbox: list[float] | None) -> float:
    if not bbox or len(bbox) < 4:
        return 0.002  # 2 mm default
    scale = max(bbox[2] - bbox[0], bbox[3] - bbox[1])
    return max(0.002, scale * 0.0005)
```

### 6.2 ezdxf Kullanımı (Özet)

```python
import ezdxf
from ezdxf.path import make_path

doc = ezdxf.readfile(path, recover=True)
msp = doc.modelspace()

for entity in msp:
    if entity.dxftype() in ("LINE", "LWPOLYLINE", "POLYLINE", "ARC", "CIRCLE", "SPLINE"):
        path = make_path(entity)
        for vertex in path.flattening(distance=chord_tolerance):
            # vertex → SegmentIn (scale to metre)
```

INSERT için:
```python
for insert in msp.query("INSERT"):
    for virtual in insert.virtual_entities():
        # virtual zaten transform uygulanmış
```

### 6.3 Fallback: ezdxf Yoksa

- `ezdxf` import hatası → mevcut `parse_dxf_ascii` + sadece LINE/LWPOLYLINE(bulge=0)/POLYLINE
- Kullanıcıya uyarı: "Tam DXF desteği için ezdxf yükleyin: pip install ezdxf"

---

## 7. Performans / Limitler

- `segment_budget`: normalize aşamasında zaten var
- Discretization segment patlarsa: önce tolerance artır (2x), sonra segment_budget
- `MAX_PATH_POINTS` / `ScenarioLimits`: mevcut pipeline'da korunur
- Insight: `SEGMENT_BUDGET_APPLIED` uyarısı

---

## 8. Çıkış Kriterleri

- [ ] "L28YO-tree-of-life..." gibi SPLINE ağırlıklı DXF "segment yok" dememeli
- [ ] Kontur kaba da olsa görünür
- [ ] `verify_dxf_drawability.py`: entity_counts_supported artmış, PASS/WARN
- [ ] normalize/path/analyze/export API sözleşmeleri bozulmamalı

---

## 9. DWG → DXF Sonraki Adım (Özet)

DWG desteği için mevcut `dwg_converter.py` kullanılıyor. Önerilen yöntemler:

| Yöntem | Lisans | Platform | Not |
|--------|--------|----------|-----|
| **ODA File Converter** | Ücretsiz (ODA üyeliği) | Win/Linux/Mac | Resmi, güvenilir; CLI |
| **LibreDWG** | GPLv3 | Çapraz | Açık kaynak; DWG yazma sınırlı |
| **Teigha** | Ticari / ODA | Çapraz | ODA tabanlı |
| **Cloud Convert API** | Ücretli | SaaS | Kolay entegrasyon |
| **AutoCAD Batch** | Ticari | Win | Kullanıcıda AutoCAD gerekir |

**Öneri:** ODA File Converter — ücretsiz, resmi, `dwg_converter.py` ile subprocess çağrısı yapılabilir. Zaten projede `dwg_converter` var; hangi CLI kullanıldığına bakılmalı.

---

## 10. Özet Tablo

| PR | Kapsam | Tahmini süre |
|----|--------|---------------|
| PR-1 | ezdxf + altyapı | 1–2 gün |
| PR-2 | ARC + CIRCLE | 1 gün |
| PR-3 | LWPOLYLINE bulge | 1 gün |
| PR-4 | SPLINE | 1–2 gün |
| PR-5 | INSERT explode | 2–3 gün |
| PR-6 | Insight güncelleme | 1 gün |
| PR-7 | Entegrasyon + verify | 1 gün |
| **Toplam** | | **8–11 gün** |
