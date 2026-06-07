# Pen-safe compile guarantee

## Amaç

İnşaat planları genelde birbirinden kopuk çizgiler (stroke) içerir. Plan derlemesi
(`compile_plan`, import pipeline) her stroke için şu sırayı garanti eder:

1. Stroke başlangıcına **kalem yukarıdayken** travel (`PEN UP` → `MOVE*`)
2. Stroke başında `PEN DOWN`
3. Stroke boyunca çizim `MOVE*` komutları
4. Stroke sonunda `PEN UP`
5. Sonraki stroke'a yine **kalem yukarıdayken** travel

Kopuk iki çizgi arasında pen-down travel üretilmez.

## Resmi akış

- `PathGenerator.generate_path_segments()` stroke sınırlarını korur.
- `compile_segments_pen_safe()` segment listesinden komut üretir.
- `validate_pen_safe_commands()` çıktıyı gramer olarak doğrular.

Düz nokta listesi (`generate_path()` + tek stroke derleyici) çoklu kopuk stroke için
kullanılmaz; stroke bilgisi kaybolur.

## Sınırlar

Bu garanti **yazılım derlemesi** içindir. Fiziksel servo/kalem davranışının yerine
geçmez; gerçek donanımda pen-up/pen-down zamanlaması ve kalibrasyon ayrıca doğrulanmalıdır.

## İlgili dosyalar

- `backend/app/execution/compiler.py`
- `backend/app/execution/pen_safe_validator.py`
- `backend/app/execution/path_compiler.py` (PlannedPath alternatifi; aynı pen-safe sözleşme)
- `backend/app/api/main.py` — `/api/compile_plan`, import endpoint'leri
