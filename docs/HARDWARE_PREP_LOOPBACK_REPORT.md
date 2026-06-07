# Hardware Prep Loopback Report

## Date

2026-05-05

## Scope

Bu rapor yalnizca Asama 2 serial loopback hazirligi ve guvenli dogrulama incelemesini kapsar.

Bu rapor gercek robot testi degildir. Gercek robota baglanilmadi, motor controller kullanilmadi, firmware degistirilmedi ve fiziksel robota komut gonderilmedi.

Bu asamada iki mod ayrilir:

- Guvenli hazirlik modu: Mevcut loopback scriptleri, serial driver/protokol kodu, testler ve dokumantasyon incelenir. Gercek port kullanilmaz.
- Opsiyonel loopback calisma modu: Yalniz kullanici acikca port verdiyse, portun robot/motor controller olmadigi dogrulandiysa ve baglanti sanal COM veya USB-serial TX-RX loopback ise calistirilir.

Bu raporda opsiyonel loopback calisma modu calistirilmadi, cunku kullanici tarafindan acik loopback portu verilmedi.

## Preconditions

- Robot bagli olmamali.
- Motor controller bagli olmamali.
- Firmware degistirilmemeli.
- Sanal COM veya USB-serial TX-RX loopback kullanilmali.
- Kucuk plan kullanilmali.
- Asama 0 baseline dogrulama `BASELINE PASS` olmali.
- Asama 1 dry-run serial dogrulama `DRY_RUN PASS` olmali.
- Port acikca kullanici tarafindan verilmeli.
- Portun robot, motor controller veya firmware karti olmadigi dogrulanmali.
- `dry_run=false` yalniz guvenli loopback portunda ve robot bagli degilken degerlendirilmelidir.

## Files Inspected

- `backend/scripts/smoke_test_serial_loopback.py`
- `backend/app/drivers/serial_driver.py`
- `backend/app/drivers/serial_protocol.py`
- `backend/app/drivers/serial_driver_stub.py`
- `backend/tests/test_serial_driver.py`
- `backend/tests/test_serial_protocol_transport.py`
- `backend/tests/test_serial_driver_stub.py`
- `backend/tests/test_execute_serial_api.py`
- `docs/SERIAL_PROTOCOL_V1.md`

## Serial Protocol Summary

Host tarafindaki ana sozlesme canonical `List[Command]` modelidir. Bu model `serialize_commands` ile DSL metnine cevrilir, sonra serial wire payload olarak UTF-8 byte dizisine donusturulur.

Protokol ozeti:

- Profil A: Host yalniz DSL satirlarini gonderir. `BEGIN` / `END` kullanmaz.
- Profil B: Host `BEGIN`, DSL satirlari ve `END` gonderir. Mevcut `SerialDriver` varsayilan olarak Profil B kullanir.
- `BEGIN`: Batch komut blogunun baslangicidir.
- `END`: Batch komut blogunun bittigini bildirir.
- `DONE`: MCU veya loopback tarafindan batch tamamlandiginda beklenen basari cevabidir.
- `OK`: Profil A veya ara satir kabul cevaplari icin desteklenen cevaptir; driver `DONE` beklerken `OK` satirlarini gecici/ara cevap olarak kabul edip okumaya devam eder.
- `ERR <mesaj>`: Komut veya calisma hatasidir. `SerialDriver` bunu `RuntimeError("MCU ERR: ...")` olarak ust katmana tasir.
- `STATUS key=value ...`: Opsiyonel durum cevabidir. Scriptin `status` modu tek satir `STATUS` sorgusu gonderip `STATUS ...` cevabi bekler.
- Timeout: `readline()` bos donerse `SerialDriver` `TimeoutError("MCU yaniti yok ...")` uretir.
- STOP: `STOP\n` tek satir olarak gonderilir. Driver, `expect_done_after_batch=true` iken STOP sonrasi da `DONE` bekler.

Frame davranisi:

```text
BEGIN
SPEED 1
MOVE 10 0
END
```

Beklenen basarili Profil B cevabi:

```text
DONE
```

Beklenen hata cevabi:

```text
ERR parse
```

## Loopback Script Summary

`backend/scripts/smoke_test_serial_loopback.py` positional `port` argumani ister. Port verilmeden gercek loopback calistirilamaz.

Guvenli olarak yalniz `--help` calistirildi:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\smoke_test_serial_loopback.py --help
```

Script argumanlari:

- `port`: `COM3`, `/dev/ttyUSB0`, vb. Zorunlu.
- `--baudrate`: Varsayilan `115200`.
- `--timeout`: Okuma zaman asimi, varsayilan `2.0`.
- `--mode`: `normal`, `stop`, `malformed`, `status`.

Modlar:

- `normal`: `SerialDriver` batch gonderir ve `DONE` bekler.
- `stop`: Batch sonrasi `STOP` gonderir ve `DONE` bekler.
- `malformed`: Ham serial ile bozuk `BEGIN\nMOVE\nEND\n` payload gonderir ve `ERR` bekler.
- `status`: `STATUS\n` gonderir ve `STATUS ...` cevabi bekler.

## Loopback Execution Plan

Guvenli loopback testi yalniz asagidaki kosullar saglandiginda calistirilmalidir:

- Robot bagli degil.
- Motor controller bagli degil.
- Firmware karti canli robot kontrolunde degil.
- Kullanilan port sanal COM cifti veya USB-serial TX-RX loopback.
- Port adi kullanici tarafindan acikca verildi.
- Portun robot/motor controller olmadigi manuel olarak dogrulandi.
- Asama 0 `BASELINE PASS`.
- Asama 1 `DRY_RUN PASS`.

Onerilen minimum plan:

```text
LINE 0 0 100 0
```

Onerilen sira:

1. `LINE 0 0 100 0` plani `/api/compile_plan` ile canonical command metnine cevir.
2. `/api/analyze` ile `collision_mode="error"` preflight sonucunu temiz dogrula.
3. `/api/execute_serial` ile `dry_run=true` calistir ve `trace_id`, `commands_sha256`, `preflight_summary` kaydet.
4. Loopback portunu hazirla.
5. Portun robot/motor controller olmadigini dogrula.
6. Script `normal` modunu loopback portuyla calistir.
7. `DONE` cevabini dogrula.
8. Script `malformed` modunu calistir ve `ERR` cevabini dogrula.
9. Gerekirse `stop` modunda STOP sonrasi `DONE` cevabini dogrula.
10. Gerekirse `status` modunda `STATUS ...` cevabini dogrula.

Sanal COM cifti icin:

- Iki ucun birbirine bagli oldugu dogrulanmali.
- Host scriptinin yazdigi portun karsi ucunda loopback/firmware emulator cevabi uretebildigi kanitlanmali.
- Port adi test notuna yazilmali.

USB-serial TX-RX loopback icin:

- Yalniz TX ve RX pinleri kendi aralarinda loopback yapilmali.
- Motor, batarya, robot karti veya actuator baglanmamali.
- GND/voltaj seviyeleri donanima zarar vermeyecek sekilde dogrulanmali.
- Bu modda MCU `DONE` cevabi otomatik uretilmeyebilir; yalniz fiziksel wire echo testi icin kullaniliyorsa script beklentileri ayrica degerlendirilmelidir.

## Loopback Test Result

LOOPBACK NOT RUN - PORT NOT PROVIDED

Gerekce:

- Kullanici tarafindan acik loopback portu verilmedi.
- Portun robot/motor controller olmadigi dogrulanamadi.
- Bu nedenle gercek serial port acilmadi ve loopback calistirilmadi.

## Safety Confirmation

- Gercek robota baglanilmadi.
- Motor controller kullanilmadi.
- Firmware degistirilmedi.
- Buyuk plan kullanilmadi.
- `dry_run=false` calistirilmadi.
- Gercek serial port acilmadi.
- Remote execution acilmadi.
- Legacy klasorlere dokunulmadi.
- `webapp/frontend/` altinda islem yapilmadi.
- `webapp/backend/` altinda islem yapilmadi.

## Final Verdict

LOOPBACK PREPARED BUT NOT EXECUTED

## Recommended Next Step

Once sanal COM veya USB-serial TX-RX loopback ortami hazirlanmali ve port adi acikca belirlenmelidir.

Loopback portu hazir oldugunda, portun robot/motor controller olmadigi manuel olarak dogrulanmali ve bu rapordaki loopback execution plan sirayla uygulanmalidir. Ancak gercek loopback testi basariyla gecerse Asama 3: Robot bagli ama off-ground guvenli fiziksel test degerlendirilebilir.
