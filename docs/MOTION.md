# Hareket planlama (diferansiyel sürüş hazırlığı)

## Offline motion demo

Geliştirici/öğrenci demoları için `backend/scripts/offline_motion_demo.py`: küçük yerleşik senaryoları (kare, dikdörtgen, L, dön–ileri) **motion facade** ile çalıştırır; HTTP ve donanım yoktur. Eski `CommandExecutor` tabanlı simülatörden ayrıdır. Senaryo tanımında beklenen son `(x, y)` / isteğe bağlı `theta_deg` varsa, çalıştırma sonrası toleranslı karşılaştırma özeti (`PASS` / `WARN` / `FAIL`) yazdırılır; `--no-check` ve `--strict` bayraklarına bakın.

## Bu katman neden var

Resmi komutlar (`MoveCommand`, `TurnCommand`, vb.) **dünya çerçevesinde geometri** tanımlar. Mevcut `CommandExecutor` ise **simülasyon** için düzlemde doğrudan hedefe doğru ilerler; tekerlek kısıtı yoktur (holonomik nokta-robot yaklaşımı).

**Diferansiyel sürüşlü** bir zemin çizim robotunda hareket kısıtlıdır; tipik yürütme **önce başlığa dön, sonra ileri git** şeklindedir. `app.motion` paketi, bu strateji için tek komut + mevcut pozdan `(turn_delta_deg, forward_distance_m)` üreten **saf geometri** içerir.

## `CommandExecutor` ile farkı

| Parça | Rol |
|--------|------|
| `CommandExecutor` | Tick tabanlı simülasyon; holonomik tarzda düz çizgi ile hedefe gider. |
| `app.motion.*` | Rotate-then-go için çevrimdışı geometrik hedefler; **zaman adımı yok**, **motor yok**. |

## Rotate-then-go varsayımı

Her `MoveCommand` / `MoveRelCommand` şöyle ayrıştırılır:

1. Hedef doğrultuya en kısa açı farkı ile dön.
2. Öklid mesafesi kadar ileri git.

`TurnCommand` ve `ForwardCommand` sırasıyla `(delta_deg, 0)` ve `(0, mesafe)` olarak eşlenir.

## Segment kontrolör iskeleti (`segment_controller`)

`RotateThenGoSegment` + `step_segment_controller` ile **saf Python** üzerinden faz (dönüş / ileri / bitti) ve basit `linear_velocity_m_s` / `angular_velocity_deg_s` çıktıları üretilir. Bu katman hâlâ **gerçek motor veya tekerlek kinematiği içermez**; zaman entegrasyonu, PID ve seri/ROS bağlantısı yoktur.

Durum modeli: segment başladığında başlangıç pozu sabitlenir; hedef başlık ve hedef nokta bu başlangıçtan türetilir, tamamlanma **mutlak hedefe göre** ölçülür (her adımda pozdan yeniden hesaplanır). İleride donanım veya üst seviye kontrolör bu çıktıları tüketebilir.

## Motion runner (`motion_runner`)

Kontrolör iskeleti **tek adımda** ne yapılacağını söyler; **motion runner** ise bunu küçük `dt` ile tekrarlayıp pozu Euler ile güncelleyerek kapalı döngü **simülasyon** akışı oluşturur (`run_rotate_then_go_segments`, `run_single_segment`).

- Kontrolör: faz + hız komutları; entegrasyon yok.
- Runner: kontrolör + basit dünya çerçevesi Euler entegrasyonu; gürültü, tekerlek modeli ve gerçek donanım yok.

Bu hâlâ **salt yardımcı / simülasyon** amaçlıdır; seri, ROS2, motor sürücü veya mevcut HTTP/`CommandExecutor` yoluna bağlanmaz. Gerçek donanım entegrasyonu **gelecek iş**tir.

## Komut dizisi yorumlayıcısı (`command_sequence_runner`)

`run_command_sequence`, resmi `List[Command]` akışını (SPEED, PEN, MOVE, MOVE_REL, TURN, FORWARD, WAIT) **yeni motion katmanı** üzerinden sırayla işler: haritalama → `RotateThenGoSegment` → `run_single_segment`. Bu, eski `CommandExecutor` simülasyonundan **ayrı** bir saf Python yoludur; HTTP, sürücü ve dışa aktarma ile bağlantısı yoktur.

`WaitCommand` yalnızca `simulated_time_s` birikimini artırır (iş parçacığı / gerçek zaman bekleme yok). `SpeedCommand` taban kontrolör hızlarına **çarpan** uygular.

Amaç: ileride gerçek robot yürütmesine köprü olabilecek **deterministik** bir yorumlayıcı; donanım entegrasyonu hâlâ bu modülün dışındadır.

## Yürütme facade (`execution_facade`)

`command_sequence_runner` **düşük seviye** yorumlayıcıdır (`run_command_sequence`). **`execute_command_sequence_motion`** ise yeni motion yolunun **tek üst seviye giriş noktasıdır**: varsayılan kontrolör, başlangıç pozu ve bütçe parametreleri tek çağrıda toplanır; sonuç ``MotionExecutionResult`` ile özetlenir (içeride ``CommandSequenceResult`` ile aynı veri, ``final_pose`` adıyla).

Bu facade, eski ``CommandExecutor`` ve gerçek sürücü/dispatch yolundan **ayrı** kalır; HTTP rotalarına bağlanmaz. İsteğe bağlı ``driver_context`` parametresi ileride köprü için ayrılmıştır; bu sürümde **kullanılmaz**.

## Motion–dispatch köprüsü (`motion_dispatch_bridge`)

``execute_and_optionally_dispatch`` önce motion facade’i çalıştırır; ``dispatch_enabled`` ve bir ``RobotDriver`` verilirse aynı ``List[Command]`` için ``dispatch_commands`` çağrılır. Bu katman **geliştirme / test mimarisi** içindir; HTTP’ye bağlı değildir, eski ``CommandExecutor``’ı değiştirmez; kontrollü entegrasyon için bir sınır tanımlar. Dispatch hataları istisna olarak yükselmez; ``MotionDispatchBridgeResult.dispatch_error`` içinde tutulur, motion sonucu etkilenmez.

## Sonraki adımlar

Fiziksel bir kontrolör bu segmentleri ve hız komutlarını tüketip tekerlek hızları, zamanlı yaylar veya gerçek sürücü komutları üretir; bu modülün bugünkü kapsamının **dışındadır**.
