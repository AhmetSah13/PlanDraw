# Firmware Build — arduino-cli

Bu belge, `firmware/newbot_real_v1` ve `firmware/newbot_loopback_v1` sketch'lerinin **arduino-cli** ile nasıl derleneceğini açıklar.

## Doğrulanmış hedef kart (ESP32-S3 DevKitC-1 N16R8)

Aşağıdaki FQBN, `arduino-cli board listall esp32` ve `board details` çıktısı ile doğrulanmıştır.
Temel board: **ESP32S3 Dev Module** (`esp32:esp32:esp32s3`); N16R8 modülü için flash/PSRAM seçenekleri eklenir.

```
esp32:esp32:esp32s3:FlashSize=16M,PSRAM=opi,PartitionScheme=default
```

| Sketch | Compile durumu (arduino-cli 1.5.1, esp32 core 3.3.8) |
|--------|------------------------------------------------------|
| `firmware/newbot_real_v1` | **PASS** (~304 KB flash, ~27 KB RAM) |
| `firmware/newbot_loopback_v1` | **PASS** (~302 KB flash, ~26 KB RAM) |

Farklı bir kart veya modül kullanılıyorsa FQBN yeniden doğrulanmalıdır; aşağıdaki şablonlarda `<TARGET_FQBN>` placeholder korunur.

### Donanım notu (Patch 4A)

- Kart: **ESP32-S3 DevKitC-1 N16R8** (`robot_config.h` → `BOARD_TARGET_NOTE`)
- Motor: 2× NEMA17 + 2× TMC2208 (STEP/DIR/EN)
- Kalem: servo — pinler Patch 4B'de `robot_config.h` içine girilecek

## Ön koşullar

1. [arduino-cli](https://github.com/arduino/arduino-cli/releases) kurulu ve PATH'te.
2. Hedef kart için doğru **board core** yüklü.
3. Sketch klasörü Arduino multi-file yapısında (`*.ino` + aynı klasördeki `.cpp/.h`).

### PATH kontrolü

```powershell
arduino-cli version
```

Komut bulunamazsa CLI kurulmamış veya PATH'e eklenmemiştir.

### Kurulum (Windows örneği)

```powershell
winget install ArduinoSA.CLI
```

Alternatif: GitHub release indirip `arduino-cli.exe` yolunu PATH'e ekleyin.

### Core hazırlığı

```powershell
arduino-cli core update-index
arduino-cli core install <CORE_PACKAGE>
```

`<CORE_PACKAGE>` hedef karta bağlıdır (ör. `esp32:esp32` — **kartınızı doğrulayın**).

Desteklenen kartları listelemek için:

```powershell
arduino-cli board listall
```

## Compile komut şablonları

Proje kökünden (DevKitC-1 N16R8 — doğrulanmış FQBN):

```powershell
$Fqbn = "esp32:esp32:esp32s3:FlashSize=16M,PSRAM=opi,PartitionScheme=default"

# Gerçek kart firmware iskeleti
arduino-cli compile --fqbn $Fqbn firmware/newbot_real_v1

# Loopback / protokol doğrulama sketch'i
arduino-cli compile --fqbn $Fqbn firmware/newbot_loopback_v1
```

Başka kart için `<TARGET_FQBN>` ile aynı komut yapısı kullanılır.

Başarılı derleme sonrası build çıktısı sketch klasörünün `build/` altında oluşur (arduino-cli sürümüne göre yol değişebilir).

## Upload komut şablonu

```powershell
arduino-cli upload -p <PORT> --fqbn <TARGET_FQBN> firmware/newbot_real_v1
```

`<PORT>` örnekleri: `COM7`, `/dev/ttyUSB0` — Aygıt Yöneticisi veya `arduino-cli board list` ile tespit edin.

## Serial monitor (isteğe bağlı)

```powershell
arduino-cli monitor -p <PORT> -c baudrate=115200
```

Firmware ve host smoke testleri **115200** baud kullanır.

## Build helper script

Parametre zorunlu FQBN ile (DevKitC-1 N16R8 örneği):

```powershell
$Fqbn = "esp32:esp32:esp32s3:FlashSize=16M,PSRAM=opi,PartitionScheme=default"

.\scripts\firmware_compile.ps1 -Sketch firmware\newbot_real_v1 -Fqbn $Fqbn
.\scripts\firmware_compile.ps1 -Sketch firmware\newbot_loopback_v1 -Fqbn $Fqbn
```

FQBN verilmezse script güvenli şekilde hata verir; varsayılan FQBN kullanmaz.

## Smoke test ön koşulları

Derleme/upload tek başına protokol doğrulaması değildir. Upload sonrası:

1. Doğru COM portunu tespit edin.
2. `docs/HARDWARE_PREP_SERIAL_SMOKE.md` prosedürünü uygulayın.
3. `backend/scripts/smoke_test_serial_loopback.py` ile STATUS / normal / stop / malformed modlarını çalıştırın.

## İlgili belgeler

- `firmware/newbot_real_v1/README.md` — sketch kapsamı
- `firmware/newbot_loopback_v1/README.md` — loopback sketch
- `docs/HARDWARE_PREP_SERIAL_SMOKE.md` — serial/socket smoke prosedürü
- `docs/SERIAL_PROTOCOL_V1.md` — wire protokolü
